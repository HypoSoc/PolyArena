from __future__ import annotations

import os
from queue import PriorityQueue
from typing import TYPE_CHECKING, Dict, Tuple, List, FrozenSet, Callable, Set, Any, Optional

from constants import Condition, Effect, InfoScope, Trigger, DamageType, InjuryModifier, \
    SELF_PLACEHOLDER, TARGET_PLACEHOLDER, NONCOMBAT_TRIGGERS, Element
from items import get_item

if TYPE_CHECKING:
    from player import Player
    from skill import Skill

DEBUG = False

ATTACK_PRIORITY = 100
DAMAGE_PRIORITY = 150
WOUND_PRIORITY = 160

Event_List = List[Tuple[str, List['Player'], InfoScope]]

# Type for priority queue, takes PRIORITY, INDEX (to ensure total ordering even with equal priorities),
# and function to call
Tic = Tuple[int, int, Callable[[], None]]


class CombatHandler:
    REAL_HANDLER = None

    def __init__(self):
        self.tic_index = 0

        self.broadcast_events: List[str] = []

        self.hot_blood = set()
        self.report_dict = {}
        self.attacker_to_defender: Dict["Player", "Player"] = {}
        self.combat_group_to_events = {}
        self.verb_dict: Dict['Player', str] = {}  # Used if 'attacked' isn't appropriate
        self.range_edges: List[Tuple['Player', 'Player']] = []  # One directional edges used to calculate range

        self.ambushes: Dict['Player', Set['Player']] = {}  # First populated when attempting to ambush, then pruned

        self.damaged_by: Dict['Player', Set['Player']] = {}  # Used by ambush

        self.solitary_combat: Set["Player"] = set()

    def simulate_combat(self, circuit_change: Dict['Player', Tuple[Element]]) -> Dict['Player', int]:
        sim = CombatHandler()
        player_to_clone: Dict["Player", "Player"] = {}

        def make_and_modify_clone(player: 'Player'):
            clone = player.make_copy_for_simulation()
            if player in circuit_change:
                assert clone.set_attunement(circuit_change[player]), \
                    f"Somehow an illegal circuit configuration is being tested for {player.name} " \
                    f"({circuit_change[player]})"
            player_to_clone[player] = clone

        for attacker, defender in self.attacker_to_defender.items():
            if attacker not in player_to_clone:
                make_and_modify_clone(attacker)
            if defender not in player_to_clone:
                make_and_modify_clone(defender)
            sim.add_attack(player_to_clone[attacker], player_to_clone[defender])

        for self_attacker in self.solitary_combat:
            if self_attacker not in player_to_clone:
                make_and_modify_clone(self_attacker)
            sim.add_solitary_combat(player_to_clone[self_attacker])

        sim.process_all_combat()
        return {player: clone.get_score() for player, clone in player_to_clone.items()}

    def add_attack(self, attacker: "Player", defender: "Player"):
        self.hot_blood.add(attacker.name)
        self.hot_blood.add(defender.name)
        self.attacker_to_defender[attacker] = defender

    # Used if someone gets into combat all on their own, e.g. using Poison Gas without being attacked
    def add_solitary_combat(self, player: "Player"):
        self.solitary_combat.add(player)

    def player_in_combat(self, player: "Player"):
        for a, d in self.attacker_to_defender.items():
            if player in (a, d):
                return True
        return player in self.solitary_combat

    def player_innocent(self, player: "Player"):
        return player not in self.attacker_to_defender

    def update_verb_dict(self, player: "Player", verb: str):
        if player not in self.verb_dict:
            self.verb_dict[player] = verb
            player.action.public_description = player.action.public_description.replace("attacked", verb)

        else:
            if verb not in self.verb_dict[player]:
                new_verbs = self.verb_dict[player] + " and " + verb
                player.action.public_description = player.action.public_description.replace(self.verb_dict[player],
                                                                                            new_verbs)
                self.verb_dict[player] = new_verbs

    def process_all_combat(self):
        # Calculate Combat Groups
        combat_groups = []
        for (attacker, defender) in self.attacker_to_defender.items():
            self.solitary_combat.discard(attacker)
            self.solitary_combat.discard(defender)
            new_group = True
            for _group in combat_groups:
                if attacker in _group or defender in _group:
                    new_group = False
                    _group.add(attacker)
                    _group.add(defender)
            if new_group:
                combat_groups.append({attacker, defender})
            self.range_edges.append((attacker, defender))
            self.range_edges.append((defender, attacker))

        for solitary in self.solitary_combat:
            combat_groups.append({solitary})

        # Prevents double attack if two players attack each other
        # Not used for skill evaluation, only damage dealing
        simplified_attack_to_defend: Dict[Player, Player] = {}
        for (attacker, defender) in self.attacker_to_defender.items():
            if simplified_attack_to_defend.get(defender) != attacker:
                simplified_attack_to_defend[attacker] = defender

        for _group in combat_groups:
            # For generating reports
            group: FrozenSet[Player] = frozenset(_group)
            self.combat_group_to_events[group] = []

            combat = {}
            survivability = {}
            conditions: Dict['Player', List[Condition]] = {}

            queue: PriorityQueue[Tic] = PriorityQueue()

            # Prevent certain things from happening redundantly, like armor break
            only_once: Set[Any] = set()
            # Special Disarm Theft logic
            # Victim: Thieves
            disarm_thief: Dict[Player, List[Player]] = {p: [] for p in group}

            # For looting
            dead_list = []

            def get_damage_type(a: 'Player', initial_damage_type: DamageType = DamageType.DEFAULT) -> DamageType:
                if Condition.PETRIFY in conditions[a]:
                    return DamageType.PETRIFY
                return initial_damage_type

            def get_injury_modifiers(a: 'Player') -> List[InjuryModifier]:
                modifiers = []
                if Condition.INFLICT_GRIEVOUS in conditions[a]:
                    modifiers.append(InjuryModifier.GRIEVOUS)
                if Condition.INFLICT_CAUTERIZE in conditions[a]:
                    modifiers.append(InjuryModifier.PERMANENT)
                return modifiers

            # Generate a tic to remove a condition from a player
            def condition_remove_tic(priority: int, p: Player, c: Condition) -> Tic:
                self.tic_index += 1

                def condition_remove():
                    if c in conditions[p]:
                        conditions[p].remove(c)
                return priority+1, self.tic_index, condition_remove

            # Generate a tic to remove an item from a player's inventory
            def item_remove_tic(priority: int, p: Player, item_index: int) -> Tic:
                self.tic_index += 1

                def item_remove():
                    if item_index in p.items:
                        p.items.remove(item_index)
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   f"{p.name}'s {get_item(item_index).name} was "
                                                   f"{get_item(item_index).destruction_message}.",
                                                   [p], InfoScope.PRIVATE)
                return priority+1, self.tic_index, item_remove

            # We need priority to tic before checking, otherwise defending snipers wouldn't be able to counter-snipe
            def sniper_tic(priority: int, p: Player) -> Tic:
                self.tic_index += 1

                def snipe():
                    # Attacking the sniper or having sniper yourself lets you hit back against a sniper
                    target = self.attacker_to_defender[p]
                    if Condition.SNIPING not in conditions[target]:
                        if self.attacker_to_defender.get(target, None) != p:
                            if (target, p) in self.range_edges:
                                self.range_edges.remove((target, p))

                return priority+1, self.tic_index, snipe

            def ambush_tic(ambusher: 'Player', ambushee: 'Player', verb: str) -> Tic:
                self.tic_index += 1

                def confirm_ambush():
                    if ambushee not in self.ambushes.get(ambusher, set()):
                        return

                    if Condition.AMBUSH_AWARE in conditions[ambushee]:
                        if ambushee.get_awareness() > ambusher.get_awareness():
                            self.ambushes[ambusher].discard(ambushee)
                            self._append_to_event_list(self.combat_group_to_events[group],
                                                       f"{ambusher.name} failed to ambush {ambushee.name}.",
                                                       [ambusher, ambushee], InfoScope.PUBLIC)
                            return

                    # Ambushes cancel each other out
                    if ambusher in self.ambushes.get(ambushee, set()):
                        self.ambushes[ambushee].discard(ambusher)
                        self.ambushes[ambusher].discard(ambushee)
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   f"{ambusher.name} and {ambushee.name} failed to "
                                                   f"ambush each other.",
                                                   [ambusher, ambushee], InfoScope.PUBLIC)
                        return
                    if 'counter' not in verb:
                        self.update_verb_dict(ambusher, verb)
                    conditions[ambushee].append(Condition.AMBUSHED)

                return 6, self.tic_index, confirm_ambush

            def skill_tic(p: Player, skill: 'Skill') -> Tic:
                self.tic_index += 1

                def handle_skill():
                    if skill.trigger == Trigger.NONCOMBAT:
                        return

                    if skill.fragile and skill.fragile in conditions[p]:
                        return

                    if skill.self_has_condition and skill.self_has_condition not in conditions[p]:
                        return
                    if skill.self_not_condition and skill.self_not_condition in conditions[p]:
                        return

                    targets: List['Player'] = []
                    if skill.trigger == Trigger.SELF:
                        targets = [p]
                    elif skill.trigger == Trigger.ATTACK:
                        if p in self.attacker_to_defender:
                            targets = [self.attacker_to_defender[p]]
                    elif skill.trigger == Trigger.ATTACKED:
                        for a, d in self.attacker_to_defender.items():
                            if d == p:
                                if a not in targets:
                                    targets.append(a)
                    elif skill.trigger == Trigger.ENEMY:
                        if p in self.attacker_to_defender:
                            targets.append(self.attacker_to_defender[player])
                        for o in self.attacker_to_defender:
                            if self.attacker_to_defender[o] == player:
                                targets.append(o)
                    elif skill.trigger == Trigger.RANGE:
                        targets = [o for o in group if self.check_range(p, o)]
                    elif skill.trigger == Trigger.RANGE_EX_SELF:
                        targets = [o for o in group if self.check_range(p, o) and o.name != p.name]
                    elif skill.trigger == Trigger.COMBAT_INJURY:
                        targets = [p]

                    if skill.trigger != Trigger.SELF:
                        if skill.target_has_condition:
                            targets = [target for target in targets if skill.target_has_condition in conditions[target]]
                        if skill.target_not_condition:
                            targets = [target for target in targets if
                                       skill.target_not_condition not in conditions[target]]

                    if not targets:
                        return

                    for target in targets:
                        if skill.effect == Effect.INFO:
                            continue

                        if skill.effect == Effect.COMBAT:
                            # If combat value is set to -1, then it can't be changed
                            if combat[target] >= 0:
                                combat[target] += skill.value
                                # Combat can't be lowered below zero by regular means
                                if combat[target] < 0:
                                    combat[target] = 0
                        elif skill.effect == Effect.NO_COMBAT:
                            combat[target] = -1
                        elif skill.effect == Effect.SURVIVABILITY:
                            # If combat value is set to -1, then it can't be changed
                            if survivability[target] >= 0:
                                survivability[target] += skill.value
                                # Combat can't be lowered below zero by regular means
                                if survivability[target] < 0:
                                    survivability[target] = 0
                        elif skill.effect == Effect.NO_SURVIVABILITY:
                            survivability[target] = -1
                        elif skill.effect == Effect.BALANCE:
                            for i in range(skill.value):
                                if combat[target] < survivability[target]:
                                    combat[target] += 1
                                else:
                                    survivability[target] += 1
                        elif skill.effect == Effect.CONDITION:
                            condition = Condition[skill.value]
                            if condition not in conditions[target]:
                                conditions[target].append(condition)
                        elif skill.effect == Effect.REL_CONDITION:
                            condition = Condition[skill.value]
                            p.add_relative_condition(target, condition)
                        elif skill.effect == Effect.PERMANENT_CONDITION:
                            condition = Condition[skill.value]
                            conditions[target].append(condition)
                            target.conditions.append(condition)
                        elif skill.effect == Effect.DISARM:
                            queue.put(condition_remove_tic(skill.priority, target, Condition.ARMED))
                            disarm_thief[target].append(p)
                        elif skill.effect == Effect.ARMOR_BREAK:
                            queue.put(condition_remove_tic(skill.priority, target, Condition.ARMORED))
                            # Don't want to destroy redundant copies
                            tag = ("Armor Break", target.name, target.get_worn_armor().pin)
                            if tag not in only_once:
                                only_once.add(tag)
                                queue.put(item_remove_tic(skill.priority, target, target.get_worn_armor().pin))
                        elif skill.effect == Effect.WEAPON:
                            combat[target] += skill.value
                            conditions[target].append(Condition.ARMED_SET)  # Only one weapon can apply its bonus
                        elif skill.effect == Effect.ARMOR:
                            survivability[target] += skill.value
                            conditions[target].append(Condition.ARMOR_SET)  # Only one weapon can apply its bonus
                        elif skill.effect == Effect.SNIPING:
                            self.update_verb_dict(target, skill.text)
                            # Modify description of action in place to make the report read cleaner
                            conditions[target].append(Condition.SNIPING)
                            queue.put(sniper_tic(skill.priority, target))
                        elif skill.effect == Effect.NONLETHAL:
                            queue.put(damage_tic(skill.priority+1, source=p, target=target,
                                                 dmg_type=get_damage_type(p, DamageType.NONLETHAL),
                                                 injury_modifiers=get_injury_modifiers(p),
                                                 target_not_condition=skill.target_not_condition))
                        elif skill.effect == Effect.AMBUSH:
                            if p not in self.ambushes:
                                self.ambushes[p] = set()
                            self.ambushes[p].add(target)
                            queue.put(ambush_tic(p, target, skill.text))
                        else:
                            raise Exception(f"Unhandled effect type in combat! {skill.effect.name}")

                    if skill.info != InfoScope.HIDDEN:
                        for target in targets:
                            self._append_to_event_list(self.combat_group_to_events[group],
                                                       skill.text.replace(SELF_PLACEHOLDER, p.name)
                                                       .replace(TARGET_PLACEHOLDER, target.name),
                                                       [p, target],
                                                       skill.info)

                return skill.priority, self.tic_index, handle_skill

            def petrify_tic(base_priority: int, p: Player) -> Tic:
                self.tic_index += 1

                def petrify():
                    def reporting_function(message: str, info_scope: InfoScope):
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   message, [p], info_scope)

                    p.petrify(reporting_function)
                    if Condition.PETRIFIED in p.conditions:
                        conditions[p].append(Condition.GAS_IMMUNE)
                        conditions[p].append(Condition.PETRIFIED)

                return base_priority, self.tic_index, petrify

            def wound_tic(base_priority: int, p: Player, injury_modifiers: List[InjuryModifier]) -> Tic:
                self.tic_index += 1

                def wound():
                    if Condition.COMBAT_REGEN in conditions[p]:
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   "You regenerated, ignoring the wound.", [p], InfoScope.PRIVATE)
                        return

                    was_alive = not p.is_dead()

                    _injury_modifiers = injury_modifiers

                    if Condition.GRIEVOUS_IMMUNE in conditions[p] and InjuryModifier.GRIEVOUS in _injury_modifiers:
                        if InjuryModifier.PERMANENT not in _injury_modifiers:
                            _injury_modifiers = [modifier for modifier in injury_modifiers
                                                 if modifier != InjuryModifier.GRIEVOUS]

                    def reporting_function(message: str, info_scope: InfoScope):
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   message, [p], info_scope)
                    wounded = p.wound(_injury_modifiers, reporting_function)
                    if wounded and not p.is_dead():
                        for injured_skill in p.get_skills():
                            if injured_skill.trigger == Trigger.COMBAT_INJURY:
                                queue.put(skill_tic(p, injured_skill))

                    if was_alive and p.is_dead():
                        dead_list.append(p)

                return base_priority, self.tic_index, wound

            def damage_tic(base_priority: int, source: Player, target: Player, dmg_type: DamageType,
                           injury_modifiers: List[InjuryModifier],
                           target_not_condition: Optional[Condition] = None) -> Tic:
                self.tic_index += 1

                # Damage is marked here for other logic, in the tic constructor, not the tic
                # If something can create a damage_tic without damaging, something has gone wrong
                # Yes this means someone petrified by poison gas and hit by normal poison gas is damaged by both
                # But that generally doesn't matter
                # Try to avoid target_not_condition whenever possible
                if target not in self.damaged_by:
                    self.damaged_by[target] = set()
                self.damaged_by[target].add(source)

                priority = base_priority
                if dmg_type == DamageType.PETRIFY:
                    priority += 5
                if dmg_type == DamageType.NONLETHAL:
                    priority += 10

                # Permanent Grievous -> Permanent -> Grievous -> Regular Injury
                priority += 3
                for modifier in injury_modifiers:
                    priority -= int(modifier)

                def wound():
                    if not target_not_condition or target_not_condition not in conditions[target]:
                        queue.put(wound_tic(priority+1, target, injury_modifiers))

                def petrify():
                    if not target_not_condition or target_not_condition not in conditions[target]:
                        queue.put(petrify_tic(priority+1, target))

                def nonlethal():
                    if not target_not_condition or target_not_condition not in conditions[target]:
                        if Condition.INJURED not in target.conditions:
                            queue.put(wound_tic(priority+1, target, injury_modifiers+[InjuryModifier.NONLETHAL]))

                if dmg_type == DamageType.DEFAULT:
                    return priority, self.tic_index, wound

                if dmg_type == DamageType.NONLETHAL:
                    return priority, self.tic_index, nonlethal

                if dmg_type == DamageType.PETRIFY:
                    return priority, self.tic_index, petrify

            def get_combat(p: 'Player', d: Optional['Player'] = None):
                if Condition.PETRIFIED in conditions[p]:
                    return 0
                c = combat[p]
                if c < 0:
                    return c

                if Condition.DEADLY_AMBUSH in conditions[p] and d in self.ambushes.get(p):
                    c += 2

                if d and d.check_relative_condition(p, Condition.SABOTAGED_KNOWLEDGE):
                    c -= 2
                elif d and p.check_relative_condition(d, Condition.KNOW):
                    c += 1

                if c < 0:
                    c = 0
                return c

            def get_survivability(p: 'Player', a: Optional['Player'] = None):
                if Condition.PETRIFIED in conditions[p]:
                    return 8
                s = survivability[p]
                if s >= 0:
                    if Condition.FIRE_PROOF in conditions[p]:
                        if a and Element.FIRE in a.circuits:
                            if Condition.GEO_LOCKED not in conditions[a]:
                                s += 2

                    if a and a.check_relative_condition(p, Condition.SABOTAGED_KNOWLEDGE):
                        s -= 2
                    elif a and p.check_relative_condition(a, Condition.KNOW):
                        s += 1

                    if s < 0:
                        s = 0

                if Condition.FIRE_BODY in conditions[p]:
                    if not a or Condition.GEO_LOCKED in conditions[a] or Element.WATER not in a.circuits:
                        s = max(s, get_combat(p, a))

                return s

            def combat_tic(offense: Player, defense: Player, ambushed_tic=False) -> Tic:
                self.tic_index += 1

                priority = ATTACK_PRIORITY
                if ambushed_tic:
                    priority += 20

                def fight():
                    # Ambushed players attempt to damage 20 priority later
                    if not ambushed_tic and offense in self.ambushes.get(defense, set()):
                        queue.put(combat_tic(offense, defense, True))
                        return

                    if self.check_range(offense, defense):
                        if DEBUG:
                            self._append_to_event_list(self.combat_group_to_events[group],
                                                       f"{offense.name} ({get_combat(offense, defense)}) attacking "
                                                       f"{defense.name} ({get_survivability(defense, offense)})",
                                                       [offense, defense],
                                                       InfoScope.PRIVATE)
                        if self._one_on_one(offense, defense, get_combat, get_survivability,
                                            self.combat_group_to_events[group]):
                            queue.put(damage_tic(DAMAGE_PRIORITY, source=offense, target=defense,
                                                 dmg_type=get_damage_type(offense),
                                                 injury_modifiers=get_injury_modifiers(offense)))
                            # Damaged by is handled inside the damage_tic CONSTRUCTOR
                            if defense in disarm_thief[offense]:
                                disarm_thief[offense].remove(defense)  # Injured attacker, so not disarm stolen
                        else:
                            if offense in disarm_thief[defense]:
                                disarm_thief[defense].remove(offense)  # Failed to injure defender, so not disarm stolen

                return priority, self.tic_index, fight

            def debug_tic(priority: int, p: Player):
                self.tic_index += 1

                def debug_print():
                    self._append_to_event_list(self.combat_group_to_events[group],
                                               f"{p.name} ({get_combat(p)}/{get_survivability(p)}) "
                                               f"{[i.name for i in p.get_items()]}"
                                               f"{[c.name for c in conditions[p]]}"
                                               f"{p.relative_condition_debug()}",
                                               [p])

                return priority, self.tic_index, debug_print

            for player in group:
                combat[player] = 0
                survivability[player] = 0
                conditions[player] = player.conditions[:] + player.turn_conditions[:]

                # Bunker Effect
                if Condition.BUNKERING in conditions[player]:
                    combat[player] += 1
                    survivability[player] += 2

                survivability[player] += conditions[player].count(Condition.FORGED)

                if Condition.PETRIFIED in conditions[player]:
                    conditions[player].append(Condition.GAS_IMMUNE)

                if player.circuits:
                    conditions[player].append(Condition.USING_GEO)

                # TODO check if hydro or aero for Condition.USING_HYDRO/AERO

                for _skill in player.get_skills():
                    # Apply effects from skills to players in order of skill priority
                    if _skill.trigger not in NONCOMBAT_TRIGGERS:
                        queue.put(skill_tic(player, _skill))
                    elif _skill.effect == Effect.TENTATIVE_CONDITION:
                        modified_skill = _skill.copy()
                        modified_skill.effect = Effect.CONDITION
                        modified_skill.trigger = Trigger.SELF
                        queue.put(skill_tic(player, modified_skill))

            if DEBUG:
                for player in group:
                    queue.put(debug_tic(99, player))

            for player in group:
                if player in simplified_attack_to_defend:
                    other = simplified_attack_to_defend[player]
                    queue.put(combat_tic(player, other))
                    queue.put(combat_tic(other, player))

            # Go through the priority queue
            while not queue.empty():
                tic = queue.get()[2]
                tic()

            # Disarm Stealing happens BEFORE Looting corpses
            for (victim, thieves) in disarm_thief.items():
                if thieves:
                    stolen = victim.get_held_weapon()
                    victim.items.remove(stolen.pin)
                    living_thieves = [thief for thief in thieves if thief not in dead_list]
                    if len(living_thieves) == 1:
                        thief = living_thieves[0]
                        thief.items.append(stolen.pin)
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   f"{thief.name} stole {victim.name}'s "
                                                   f"{stolen.name}.",
                                                   [victim, thief], InfoScope.PRIVATE)
                    elif victim not in dead_list:
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   f"{victim.name}'s {stolen.name} was lost.",
                                                   [victim], InfoScope.PRIVATE)

            survivors = [player for player in group if player not in dead_list]
            for player in dead_list:
                loot_items = [item for item in player.get_items() if item.loot]
                player.items = []
                # Looting can't happen if there is more than one survivor
                if len(survivors) == 1:
                    looter = survivors[0]
                    for item in loot_items:
                        looter.items.append(item.pin)
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   f"{looter.name} looted {player.name}'s "
                                                   f"{item.name}.",
                                                   [looter], InfoScope.PRIVATE)

    def check_range(self, player, target):
        # Quick little BFS to check if player can reach target using edges, with a small bit of
        # state to make things faster
        if player == target:
            return True
        if (player, target) in self.range_edges:
            return True

        visited = []
        queue = [player]

        while queue:
            current = queue.pop()
            visited.append(current)
            for nxt in [edge[1] for edge in self.range_edges if edge[0] == current]:
                if nxt == target:
                    self.range_edges.append((player, target))
                    return True
                if nxt not in visited:
                    queue.append(nxt)

        return False

    def _one_on_one(self, attacker: 'Player', defender: 'Player',
                    combat: Callable[['Player', Optional['Player']], int],
                    survivability: Callable[['Player', Optional['Player']], int],
                    event_list) -> bool:
        lost_ambush = False
        if attacker in self.ambushes.get(defender, set()) and \
                defender in self.damaged_by.get(attacker, set()):
            lost_ambush = True
        if not lost_ambush and combat(attacker, defender) >= survivability(defender, attacker):
            self._append_to_event_list(event_list, f"{attacker.name} damaged {defender.name}.",
                                       [attacker, defender])

            return True  # defender Damaged
        else:
            self._append_to_event_list(event_list, f"{attacker.name} failed to damage {defender.name}.",
                                       [attacker, defender])
            return False

    def _append_to_event_list(self, event_list: Event_List, message: str,
                              affected: List[Player],
                              info: InfoScope = InfoScope.PUBLIC):
        event_list.append((message, affected, info))
        if info == InfoScope.BROADCAST:
            self.broadcast_events.append(message)

    def hot_blood_check(self, player: "Player"):
        return player.name in self.hot_blood

    def get_combat_report_for_player(self, player: "Player"):
        report = ""
        for (group, events) in self.combat_group_to_events.items():
            if player in group:
                for other in group:
                    if other in self.attacker_to_defender:
                        report += other.action.public_description\
                                      .replace("attacked", self.verb_dict.get(other, 'attacked')) + os.linesep
                for event in events:
                    if event[2] in [InfoScope.PUBLIC, InfoScope.BROADCAST] or player in event[1]:
                        report += event[0] + os.linesep
                for other in group:
                    if not self.check_range(player, other):
                        report = report.replace(other.name, "Someone")
        return report

    def get_public_combat_report(self):
        report = ""
        for (group, events) in self.combat_group_to_events.items():
            for player in group:
                if player in self.attacker_to_defender:
                    report += player.action.public_description + os.linesep
            for event in events:
                if event[2] == InfoScope.PUBLIC:
                    report += event[0]+os.linesep
        return report

    def reset(self):
        self.tic_index = 0

        self.broadcast_events: List[str] = []

        self.hot_blood = set()
        self.report_dict = {}
        self.attacker_to_defender = {}
        self.combat_group_to_events = {}
        self.verb_dict = {}  # Used if 'attacked' isn't appropriate
        self.range_edges = []  # One directional edges used to calculate range

        self.ambushes = {}  # First populated when attempting to ambush, then pruned

        self.damaged_by = {}  # Used by ambush

        self.solitary_combat = set()


def get_combat_handler() -> CombatHandler:
    if CombatHandler.REAL_HANDLER is None:
        CombatHandler.REAL_HANDLER = CombatHandler()
    return CombatHandler.REAL_HANDLER
