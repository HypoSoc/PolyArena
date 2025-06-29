from __future__ import annotations

import os
import random
from queue import PriorityQueue
from typing import TYPE_CHECKING, Dict, Tuple, List, FrozenSet, Callable, Set, Any, Optional

from constants import Condition, Effect, InfoScope, Trigger, DamageType, InjuryModifier, \
    SELF_PLACEHOLDER, TARGET_PLACEHOLDER, NONCOMBAT_TRIGGERS, Element, CONDITION_IMMUNITY, Temperament
from items import get_item, get_item_by_name
from skill import Skill, get_skill

if TYPE_CHECKING:
    from player import Player

DEBUG = False

ATTACK_PRIORITY = 100
DAMAGE_PRIORITY = 150
WOUND_PRIORITY = 160

ABLATIVE = get_item_by_name("Ablative").pin
ABLATIVE_SKILL_A = get_skill(124)
ABLATIVE_SKILL_B = get_skill(125)

Event_List = List[Tuple[str, List['Player'], InfoScope]]

# Type for priority queue, takes PRIORITY, INDEX (to ensure total ordering even with equal priorities),
# and function to call
Tic = Tuple[float, float, Callable[[], None]]


class CombatHandler:
    REAL_HANDLER = None

    def __init__(self, for_speed=False):
        self.tic_index = 0
        self.for_speed = for_speed

        self.broadcast_events: List[Tuple[str, bool]] = []

        self.hot_blood = set()
        self.blood_thirst: Dict["Player", Set["Player"]] = {}
        self.injured_by: Dict["Player", Set["Player"]] = {}
        self.report_dict = {}
        self.attacker_to_defenders: Dict["Player", Set["Player"]] = {}
        self.combat_group_to_events = {}
        # Used if 'attacked' isn't appropriate
        self.verb_dict: Dict['Player', str] = {}
        # One directional edges used to calculate range
        self.range_edges: List[Tuple['Player', 'Player']] = []

        # First populated when attempting to ambush, then pruned
        self.ambushes: Dict['Player', Set['Player']] = {}

        self.drained_by: Dict['Player', Set['Player']] = {}
        self.drainers: Set['Player'] = set()
        self.drained: Set['Player'] = set()

        self.damaged_by: Dict['Player', Set['Player']] = {}  # Used by ambush

        self.solitary_combat: Set["Player"] = set()

        self.info_once: Set[str] = set()
        self.speed: Dict['Player', int] = {}

        self.escape: Set[Tuple['Player', 'Player']] = set()
        self.full_escape: Set['Player'] = set()
        self.no_escape: Set['Player'] = set()
        self.contingency_locked: Set['Player'] = set()

        self.wide_check = False
        self.is_real = False

    def simulate_combat(self, circuit_change: Dict['Player', Tuple[Element, ...]]) -> Dict['Player', int]:
        sim = CombatHandler(self.for_speed)
        player_to_clone: Dict["Player", "Player"] = {}

        clone_game = None

        def make_and_modify_clone(player: 'Player'):
            assert clone_game
            clone = player.make_copy_for_simulation(clone_game)
            if player in circuit_change:
                assert clone.set_attunement(circuit_change[player]), \
                    f"Somehow an illegal circuit configuration is being tested for {player.name} " \
                    f"({circuit_change[player]})"
            player_to_clone[player] = clone

        for attacker, defender_set in self.attacker_to_defenders.items():
            for defender in defender_set:
                if clone_game is None:
                    clone_game = attacker.game.clone()
                if attacker not in player_to_clone:
                    make_and_modify_clone(attacker)
                if defender not in player_to_clone:
                    make_and_modify_clone(defender)
                sim.add_attack(
                    player_to_clone[attacker], player_to_clone[defender])

        for self_attacker in self.solitary_combat:
            if clone_game is None:
                clone_game = self_attacker.game.clone()
            if self_attacker not in player_to_clone:
                make_and_modify_clone(self_attacker)
            sim.add_solitary_combat(player_to_clone[self_attacker])

        sim.process_all_combat()
        return {player: clone.get_score() for player, clone in player_to_clone.items()}

    def speed_sim(self) -> Set[Tuple['Player', 'Player']]:
        sim = CombatHandler(True)
        player_to_clone: Dict["Player", "Player"] = {}
        clone_to_player: Dict["Player", "Player"] = {}

        clone_game = None

        def make_and_modify_clone(_player: 'Player'):
            assert clone_game
            clone = _player.make_copy_for_simulation(clone_game)
            player_to_clone[_player] = clone
            clone_to_player[clone] = _player

        for attacker, defender_set in self.attacker_to_defenders.items():
            for defender in defender_set:
                if clone_game is None:
                    clone_game = attacker.game.clone()
                if attacker not in player_to_clone:
                    make_and_modify_clone(attacker)
                if defender not in player_to_clone:
                    make_and_modify_clone(defender)
                sim.add_attack(
                    player_to_clone[attacker], player_to_clone[defender])

        for self_attacker in self.solitary_combat:
            if clone_game is None:
                clone_game = self_attacker.game.clone()
            if self_attacker not in player_to_clone:
                make_and_modify_clone(self_attacker)
            sim.add_solitary_combat(player_to_clone[self_attacker])

        sim.process_all_combat()
        escape = set()
        for player, escaped in sim.escape:
            escape.add((clone_to_player[player], clone_to_player[escaped]))
        return escape

    def drain_sim(self) -> Set['Player']:
        sim = CombatHandler()
        player_to_clone: Dict["Player", "Player"] = {}
        clone_to_player: Dict["Player", "Player"] = {}

        clone_game = None

        def make_and_modify_clone(_player: 'Player'):
            assert clone_game
            clone = _player.make_copy_for_simulation(clone_game)
            player_to_clone[_player] = clone
            clone_to_player[clone] = _player

        for attacker, defender_set in self.attacker_to_defenders.items():
            for defender in defender_set:
                if clone_game is None:
                    clone_game = attacker.game.clone()
                if attacker not in player_to_clone:
                    make_and_modify_clone(attacker)
                if defender not in player_to_clone:
                    make_and_modify_clone(defender)
                sim.add_attack(
                    player_to_clone[attacker], player_to_clone[defender])

        for self_attacker in self.solitary_combat:
            if clone_game is None:
                clone_game = self_attacker.game.clone()
            if self_attacker not in player_to_clone:
                make_and_modify_clone(self_attacker)
            sim.add_solitary_combat(player_to_clone[self_attacker])

        sim.process_all_combat()
        locked = set()
        for locked_clone in sim.contingency_locked:
            locked.add(clone_to_player[locked_clone])
        return locked

    def add_attack(self, attacker: "Player", defender: "Player"):
        if attacker not in self.attacker_to_defenders:
            self.attacker_to_defenders[attacker] = set()
        self.attacker_to_defenders[attacker].add(defender)

    # Used if someone gets into combat all on their own, e.g. using Poison Gas without being attacked
    def add_solitary_combat(self, player: "Player"):
        self.solitary_combat.add(player)

    def player_in_combat(self, player: "Player"):
        for a, d_set in self.attacker_to_defenders.items():
            for d in d_set:
                if player in (a, d):
                    return True
        return player in self.solitary_combat

    def player_innocent(self, player: "Player"):
        return player not in self.attacker_to_defenders

    def update_verb_dict(self, player: "Player", verb: str):
        if player not in self.verb_dict:
            self.verb_dict[player] = verb
            player.action.public_description = player.action.public_description.replace(
                "attacked", verb)

        else:
            if verb not in self.verb_dict[player]:
                new_verbs = self.verb_dict[player] + " and " + verb
                player.action.public_description = player.action.public_description.replace(self.verb_dict[player],
                                                                                            new_verbs)
                self.verb_dict[player] = new_verbs

    def process_all_combat(self):
        # Calculate Combat Groups
        combat_groups = []
        for (attacker, defender_set) in self.attacker_to_defenders.items():
            for defender in defender_set:
                self.solitary_combat.discard(attacker)
                self.solitary_combat.discard(defender)
                candidate_groups = []
                for _group in combat_groups:
                    if attacker in _group or defender in _group:
                        candidate_groups.append(_group)

                if len(candidate_groups) > 1:
                    for discard_group in candidate_groups[1:]:
                        for player in discard_group:
                            candidate_groups[0].add(player)
                        combat_groups.remove(discard_group)

                if candidate_groups:
                    candidate_groups[0].add(attacker)
                    candidate_groups[0].add(defender)

                else:
                    combat_groups.append({attacker, defender})

                self.range_edges.append((attacker, defender))
                self.range_edges.append((defender, attacker))

        for solitary in self.solitary_combat:
            combat_groups.append({solitary})

        # Prevents double attack if two players attack each other
        # Not used for skill evaluation, only damage dealing
        simplified_attack_to_defend: Set[Tuple[Player, Player]] = set()
        for (attacker, defender_set) in self.attacker_to_defenders.items():
            for defender in defender_set:
                if (defender, attacker) not in simplified_attack_to_defend:
                    simplified_attack_to_defend.add((attacker, defender))

        for _group in combat_groups:
            # For generating reports
            group: FrozenSet[Player] = frozenset(_group)
            self.combat_group_to_events[group] = []

            combat = {}
            survivability = {}
            conditions: Dict['Player', List[Condition]] = {
                p: [] for p in group}

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

            def get_speed(a: "Player"):
                speed = self.speed.get(a, 0)
                if Condition.AMBUSHED in conditions.get(a, []):
                    speed -= 1
                if Condition.SNIPED in conditions.get(a, []):
                    speed -= 2
                speed += conditions[a].count(Condition.INCREASED_SPEED)
                if Condition.TARGET_LOCKED in conditions.get(a, []):
                    speed = 0
                return max(speed, 0)

            # Generate a tic to remove a condition from a player
            def condition_remove_tic(priority: int, p: Player, c: Condition) -> Tic:
                self.tic_index += 1

                def condition_remove():
                    if c in conditions[p]:
                        conditions[p].remove(c)
                    if c in p.conditions:
                        p.conditions.remove(c)

                return priority + 1, self.tic_index, condition_remove

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

                return priority + 1, self.tic_index, item_remove

            # We need priority to tic before checking, otherwise defending snipers wouldn't be able to counter-snipe
            def sniper_tic(priority: float, p: Player) -> Tic:
                self.tic_index += 1

                def snipe():
                    # Attacking the sniper or having sniper yourself lets you hit back against a sniper
                    for target in self.attacker_to_defenders.get(p, []):
                        if Condition.SNIPING not in conditions[target]:
                            if p not in self.attacker_to_defenders.get(target, []):
                                if (target, p) in self.range_edges:
                                    self.range_edges.remove((target, p))

                return priority + 1, self.tic_index, snipe

            def ambush_tic(ambusher: 'Player', ambushee: 'Player', verb: str) -> Tic:
                self.tic_index += 1

                def confirm_ambush():
                    if ambushee not in self.ambushes.get(ambusher, set()):
                        return

                    failed_ambush = False
                    if Condition.AMBUSH_IMMUNE in conditions.get(ambushee):
                        failed_ambush = True

                    if Condition.AMBUSH_AWARE in conditions[ambushee]:
                        if ambushee.get_awareness() > ambusher.get_awareness():
                            failed_ambush = True

                    if failed_ambush:
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

            def speed_ambush_tic(ambusher: 'Player', ambushee: 'Player') -> Tic:
                self.tic_index += 1

                def confirm_ambush():
                    if ambushee in self.ambushes.get(ambusher, set()):
                        return  # Already handled

                    if ambusher in self.ambushes.get(ambushee, set()):
                        return  # Can't speed ambush ambushers

                    if get_speed(ambusher) - get_speed(ambushee) < 2:
                        return  # Not fast enough

                    if Condition.AMBUSH_AWARE in conditions[ambushee]:
                        if ambushee.get_awareness() > ambusher.get_awareness():
                            return

                    self.update_verb_dict(ambusher, "blitzed")
                    if ambusher not in self.ambushes:
                        self.ambushes[ambusher] = set()
                    self.ambushes[ambusher].add(ambushee)
                    conditions[ambushee].append(Condition.AMBUSHED)

                return 25, self.tic_index, confirm_ambush

            def drain_tic(drainer: 'Player', will_bag: 'Player') -> Tic:
                self.tic_index += 1

                if will_bag not in self.drained_by:
                    self.drained_by[will_bag] = set()
                self.drained_by[will_bag].add(drainer)
                self.drainers.add(drainer)

                def drain():
                    if will_bag in self.drained:
                        return  # Already handled

                    if will_bag.willpower > 0:
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   f"You lost {will_bag.willpower} Willpower.",
                                                   [will_bag], InfoScope.PRIVATE)
                        if will_bag in self.drainers or len(self.drained_by[will_bag]) > 1:
                            self._append_to_event_list(self.combat_group_to_events[group],
                                                       f"{will_bag.name}'s {will_bag.willpower} Willpower "
                                                       f"was lost in the confusion.",
                                                       list(self.drained_by[will_bag]), InfoScope.PRIVATE)
                        elif len(self.drained_by[will_bag]) == 1:
                            assert drainer in self.drained_by[will_bag]
                            if drainer in self.drained_by:
                                self._append_to_event_list(self.combat_group_to_events[group],
                                                           f"{will_bag.name}'s {will_bag.willpower} Willpower "
                                                           f"was lost in the confusion.",
                                                           list(self.drained_by[will_bag]), InfoScope.PRIVATE)
                            else:
                                drainer.willpower += will_bag.willpower
                                drainer.willpower = min(
                                    drainer.willpower, drainer.max_willpower)
                                self._append_to_event_list(self.combat_group_to_events[group],
                                                           f"You stole {will_bag.willpower} Willpower. "
                                                           f"({drainer.willpower}/{drainer.max_willpower})",
                                                           [drainer], InfoScope.PRIVATE)
                        will_bag.willpower = 0
                    self.drained.add(will_bag)

                return 25, self.tic_index, drain

            def skill_tic(p: Player, skill: 'Skill', _targets: Optional[List[Player]] = None) -> Tic:
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
                    if Condition.PETRIFIED in conditions[p] and not skill.works_when_petrified:
                        return

                    targets: List['Player'] = []
                    if _targets is not None:
                        targets = _targets
                    else:
                        if skill.trigger == Trigger.SELF:
                            targets = [p]
                        elif skill.trigger == Trigger.ATTACK:
                            if p in self.attacker_to_defenders:
                                targets = [target for target in self.attacker_to_defenders[p]
                                           if self.check_range(p, target) or skill.effect == Effect.AMBUSH]
                        elif skill.trigger == Trigger.ATTACKED:
                            for a, d_set in self.attacker_to_defenders.items():
                                for d in d_set:
                                    if d == p:
                                        if a not in targets and self.check_range(d, a):
                                            targets.append(a)
                        elif skill.trigger == Trigger.ATTACKED_IGNORE_RANGE:
                            for a, d_set in self.attacker_to_defenders.items():
                                for d in d_set:
                                    if d == p:
                                        if a not in targets:
                                            targets.append(a)
                        elif skill.trigger == Trigger.ENEMY:  # EXPLICITLY IGNORES RANGE
                            if p in self.attacker_to_defenders:
                                for x in self.attacker_to_defenders[p]:
                                    if x not in targets:
                                        targets.append(x)
                            for o in self.attacker_to_defenders:
                                if p in self.attacker_to_defenders[o]:
                                    if o not in targets:
                                        targets.append(o)
                        elif skill.trigger == Trigger.RANGE:
                            targets = [
                                o for o in group if self.check_range(p, o)]
                        elif skill.trigger == Trigger.RANGE_IGNORE_SPEED:
                            targets = [o for o in group if self.check_range(
                                p, o, ignore_escape=True)]
                        elif skill.trigger == Trigger.RANGE_EX_SELF:
                            targets = [o for o in group if self.check_range(
                                p, o) and o.name != p.name]
                        elif skill.trigger == Trigger.COMBAT_INJURY:
                            targets = [p]

                        if skill.trigger != Trigger.SELF:
                            if skill.target_has_condition:
                                targets = [target for target in targets
                                           if skill.target_has_condition in conditions[target]]
                            if skill.target_not_condition:
                                targets = [target for target in targets if
                                           skill.target_not_condition not in conditions[target]]

                    if not targets:
                        return

                    targets = [
                        target for target in targets if not target.is_dead()]

                    if skill.effect == Effect.INTUITION:
                        # Ensure there is no way to tell WHICH player is which Aeromancer
                        random.shuffle(targets)

                    times = 1  # For repeated CONDITION type effects
                    if skill.value_b and isinstance(skill.value_b, int):
                        times = skill.value_b

                    for original_target in targets:
                        if skill.effect in [Effect.INFO, Effect.INFO_ONCE]:
                            continue

                        target = original_target
                        if skill.self_override:
                            target = p  # Effect based on target conditions, but impacts only self

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
                        elif skill.effect == Effect.IMBALANCE:
                            for _ in range(skill.value):
                                if combat[target] >= survivability[target]:
                                    combat[target] += 1
                                else:
                                    survivability[target] += 1
                        elif skill.effect == Effect.BALANCE:
                            for _ in range(skill.value):
                                if combat[target] < survivability[target]:
                                    combat[target] += 1
                                else:
                                    survivability[target] += 1
                        elif skill.effect in [Effect.CONDITION, Effect.TENTATIVE_CONDITION, Effect.TURN_CONDITION]:
                            condition = Condition[skill.value]
                            if condition not in CONDITION_IMMUNITY \
                                    or not CONDITION_IMMUNITY[condition] in conditions[target]:
                                if skill.value_b is None:
                                    if condition not in conditions[target]:
                                        conditions[target].append(condition)
                                        if skill.effect == Effect.TURN_CONDITION:
                                            target.turn_conditions.append(condition)
                                else:
                                    for _ in range(times):
                                        conditions[target].append(condition)
                                        if skill.effect == Effect.TURN_CONDITION:
                                            target.turn_conditions.append(condition)
                        elif skill.effect == Effect.REMOVE_CONDITION:
                            for _ in range(times):
                                queue.put(condition_remove_tic(
                                    skill.priority, target, Condition[skill.value]))
                        elif skill.effect == Effect.REL_CONDITION:
                            condition = Condition[skill.value]
                            for _ in range(times):
                                p.add_relative_condition(target, condition)
                        elif skill.effect == Effect.PERMANENT_CONDITION:
                            condition = Condition[skill.value]
                            if condition not in CONDITION_IMMUNITY \
                                    or not CONDITION_IMMUNITY[condition] in conditions[target]:
                                for _ in range(times):
                                    conditions[target].append(condition)
                                    target.conditions.append(condition)
                        elif skill.effect == Effect.DISARM:
                            queue.put(condition_remove_tic(
                                skill.priority, target, Condition.ARMED))
                            if target.get_held_weapon():
                                disarm_thief[target].append(p)
                        elif skill.effect == Effect.ARMOR_BREAK:
                            queue.put(condition_remove_tic(
                                skill.priority, target, Condition.ARMORED))
                            # Don't want to destroy redundant copies
                            tag = ("Armor Break", target.name,
                                   target.get_worn_armor().pin)
                            if tag not in only_once:
                                only_once.add(tag)
                                queue.put(item_remove_tic(
                                    skill.priority, target, target.get_worn_armor().pin))
                        elif skill.effect == Effect.WEAPON:
                            combat[target] += skill.value
                            # Only one weapon can apply its bonus
                            conditions[target].append(Condition.ARMED_SET)
                        elif skill.effect == Effect.ARMOR:
                            survivability[target] += skill.value
                            # Only one weapon can apply its bonus
                            conditions[target].append(Condition.ARMOR_SET)
                        elif skill.effect == Effect.SNIPING:
                            self.update_verb_dict(target, skill.text)
                            # Modify description of action in place to make the report read cleaner
                            conditions[target].append(Condition.SNIPING)
                            for sniped in self.attacker_to_defenders.get(target, []):
                                conditions[sniped].append(Condition.SNIPED)
                            queue.put(sniper_tic(skill.priority + 0.1, target))
                        elif skill.effect == Effect.DAMAGE:
                            queue.put(damage_tic(skill.priority + 1, source=p, target=target,
                                                 dmg_type=get_damage_type(p),
                                                 injury_modifiers=get_injury_modifiers(
                                                     p),
                                                 target_not_condition=skill.target_not_condition))
                        elif skill.effect == Effect.GRIEVOUS:
                            queue.put(damage_tic(skill.priority + 1, source=p, target=target,
                                                 dmg_type=get_damage_type(p),
                                                 injury_modifiers=get_injury_modifiers(
                                                     p) + [InjuryModifier.GRIEVOUS],
                                                 target_not_condition=skill.target_not_condition))
                        elif skill.effect == Effect.NONLETHAL:
                            queue.put(damage_tic(skill.priority + 1, source=p, target=target,
                                                 dmg_type=get_damage_type(
                                                     p, DamageType.NONLETHAL),
                                                 injury_modifiers=get_injury_modifiers(
                                                     p),
                                                 target_not_condition=skill.target_not_condition))
                        elif skill.effect == Effect.PETRIFY:
                            queue.put(damage_tic(skill.priority + 1, source=p, target=target,
                                                 dmg_type=get_damage_type(
                                                     p, DamageType.PETRIFY),
                                                 injury_modifiers=get_injury_modifiers(
                                                     p),
                                                 target_not_condition=skill.target_not_condition))
                        elif skill.effect == Effect.MINI_PETRIFY:
                            queue.put(damage_tic(skill.priority + 1, source=p, target=target,
                                                 dmg_type=get_damage_type(
                                                     p, DamageType.PETRIFY),
                                                 injury_modifiers=get_injury_modifiers(
                                                     p) + [InjuryModifier.MINI],
                                                 target_not_condition=skill.target_not_condition))
                        elif skill.effect == Effect.KILL:
                            queue.put(kill_tic(skill.priority + 1, target))
                        elif skill.effect == Effect.AMBUSH:
                            if p not in self.ambushes:
                                self.ambushes[p] = set()
                            self.ambushes[p].add(target)
                            queue.put(ambush_tic(p, target, skill.text))
                        elif skill.effect == Effect.SPEED:
                            if target not in self.speed:
                                self.speed[target] = 0
                            self.speed[target] += skill.value
                            if self.speed[target] < 0:
                                self.speed[target] = 0
                            if self.speed[target] >= 2:
                                for v in self.attacker_to_defenders.get(target, []):
                                    queue.put(speed_ambush_tic(target, v))
                        elif skill.effect == Effect.DRAIN:
                            queue.put(drain_tic(p, target))
                        elif skill.effect == Effect.INTUITION:
                            if target.concept:
                                self._append_to_event_list(self.combat_group_to_events[group],
                                                           skill.text.replace(
                                                               SELF_PLACEHOLDER, p.name)
                                                           .replace(TARGET_PLACEHOLDER, target.name)
                                                           .replace("%REPLACE_WITH_CONCEPT%", target.concept),
                                                           [p],
                                                           InfoScope.PERSONAL)
                        elif skill.effect == Effect.CONSUME:
                            for _ in range(times):
                                if Condition[skill.value] in conditions[target]:
                                    conditions[target].remove(
                                        Condition[skill.value])
                                    for condition in skill.condition_list:
                                        conditions[target].append(condition)
                        elif skill.effect == Effect.TEMP_SKILL:
                            from skill import get_skill
                            temp_skill = get_skill(skill.value)
                            if temp_skill.trigger != Trigger.POST_COMBAT:
                                raise Exception(
                                    f"Trying to apply a temp skill that won't activate! {skill.value}")
                            temp_skill.player_of_origin = p
                            target.temporary_skills.append(temp_skill)
                        elif skill.effect == Effect.DUST:
                            target.destroy_consumables_and_reactives()

                        else:
                            raise Exception(
                                f"Unhandled effect type in combat! {skill.effect.name}")

                    if skill.info != InfoScope.HIDDEN:
                        for target in targets:

                            msg = skill.text.replace(SELF_PLACEHOLDER, p.name).replace(
                                TARGET_PLACEHOLDER, target.name)
                            if skill.effect != Effect.INFO_ONCE or msg not in self.info_once:
                                message_origin = p
                                if skill.player_of_origin:
                                    message_origin = skill.player_of_origin
                                msg_grp = [p, target]
                                if skill.info == InfoScope.PERSONAL:
                                    msg_grp = [p]
                                elif skill.info in [InfoScope.IMPERSONAL, InfoScope.NARROW_IMPERSONAL, InfoScope.SUBTLE_IMPERSONAL]:
                                    msg_grp = [target]
                                self._append_to_event_list(self.combat_group_to_events[group], msg,
                                                           msg_grp,
                                                           skill.info, message_origin)
                            if skill.effect == Effect.INFO_ONCE:
                                self.info_once.add(msg)

                return skill.priority, self.tic_index, handle_skill

            def petrify_tic(base_priority: int, p: Player, long=False, mini=False) -> Tic:
                self.tic_index += 1

                def petrify():
                    def reporting_function(message: str, info_scope: InfoScope):
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   message, [p], info_scope, p)

                    p.petrify(reporting_function, mini=mini, long=long)
                    if Condition.PETRIFIED in p.conditions:
                        conditions[p].append(Condition.GAS_IMMUNE)
                        conditions[p].append(Condition.PETRIFIED)

                return base_priority, self.tic_index, petrify

            def kill_tic(base_priority: int, p: Player) -> Tic:
                self.tic_index += 1

                def kill():
                    was_alive = not p.is_dead()

                    def reporting_function(message: str, info_scope: InfoScope):
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   message, [p], info_scope, p)

                    p.kill(reporting_function)

                    if was_alive and p.is_dead():
                        dead_list.append(p)

                return base_priority, self.tic_index, kill

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
                                                   message, [p], info_scope, p)

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
                        if InjuryModifier.NONLETHAL in injury_modifiers:
                            if Condition.NONLETHAL_IMMUNE in conditions[target]:
                                return
                        queue.put(
                            wound_tic(priority + 1, target, injury_modifiers))
                        for damaged_skill in target.get_skills():
                            if damaged_skill.trigger == Trigger.COMBAT_DAMAGED:
                                queue.put(
                                    skill_tic(target, damaged_skill, [source]))

                def petrify():
                    if not target_not_condition or target_not_condition not in conditions[target]:
                        queue.put(petrify_tic(priority + 1, target, long=Condition.LONG_PETRIFY in conditions[source],
                                              mini=InjuryModifier.MINI in injury_modifiers))
                        for damaged_skill in target.get_skills():
                            if damaged_skill.trigger == Trigger.COMBAT_DAMAGED:
                                queue.put(
                                    skill_tic(target, damaged_skill, [source]))

                def nonlethal():
                    if not target_not_condition or target_not_condition not in conditions[target]:
                        if Condition.NONLETHAL_IMMUNE in conditions[target]:
                            return
                        if Condition.INJURED not in target.conditions:
                            queue.put(
                                wound_tic(priority + 1, target, injury_modifiers + [InjuryModifier.NONLETHAL]))
                            for damaged_skill in target.get_skills():
                                if damaged_skill.trigger == Trigger.COMBAT_DAMAGED:
                                    queue.put(
                                        skill_tic(target, damaged_skill, [source]))

                if dmg_type == DamageType.DEFAULT:
                    return priority, self.tic_index, wound

                if dmg_type == DamageType.NONLETHAL:
                    return priority, self.tic_index, nonlethal

                if dmg_type == DamageType.PETRIFY:
                    return priority, self.tic_index, petrify

            def get_combat(p: 'Player', d: Optional['Player'] = None):
                if Condition.PETRIFIED in conditions[p] or Condition.DELUDED in conditions[p]:
                    return -1
                c = combat[p]
                if c < 0:
                    return c

                if Condition.DEADLY_AMBUSH in conditions[p] and d in self.ambushes.get(p):
                    c += 2

                if d and Condition.USING_AERO in conditions[d] and Condition.UNNATURAL_INTUITION in conditions[p]:
                    c += 1

                if d and d.check_relative_condition(p, Condition.SABOTAGED_KNOWLEDGE):
                    c -= 2
                elif d and p.check_relative_condition(d, Condition.KNOW):
                    c += 1

                if c < 0:
                    c = 0
                return c

            def get_survivability(p: 'Player', a: Optional['Player'] = None):
                if Condition.PETRIFIED in conditions[p]:
                    return 9 - conditions[p].count(Condition.CRUMBLING)
                s = survivability[p]
                if s >= 0:
                    if a and Condition.USING_AERO in conditions[a] and Condition.UNNATURAL_INTUITION in conditions[p]:
                        s += 1

                    if a and a.check_relative_condition(p, Condition.SABOTAGED_KNOWLEDGE):
                        s -= 2
                    elif a and p.check_relative_condition(a, Condition.KNOW):
                        s += 2

                    if p.temperament == Temperament.HOT_BLOODED:
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

                    if offense.is_dead() or defense.is_dead():
                        return

                    if self.check_range(offense, defense):
                        self.hot_blood.add(offense.name)
                        self.full_escape.discard(defense)
                        self.full_escape.discard(offense)
                        self.no_escape.add(defense)
                        self.no_escape.add(offense)
                        if DEBUG:
                            self._append_to_event_list(self.combat_group_to_events[group],
                                                       f"{offense.name} ({get_combat(offense, defense)}) attacking "
                                                       f"{defense.name} ({get_survivability(defense, offense)})",
                                                       [offense, defense],
                                                       InfoScope.PRIVATE)
                        if self._one_on_one(offense, defense, get_combat, get_survivability,
                                            self.combat_group_to_events[group]):
                            queue.put(damage_tic(DAMAGE_PRIORITY, source=offense, target=defense,
                                                 dmg_type=get_damage_type(
                                                     offense),
                                                 injury_modifiers=get_injury_modifiers(offense)))
                            # Damaged by is handled inside the damage_tic CONSTRUCTOR
                            if defense in disarm_thief[offense]:
                                # Injured attacker, so not disarm stolen
                                disarm_thief[offense].remove(defense)
                            if defense not in self.injured_by:
                                self.injured_by[defense] = set()
                            self.injured_by[defense].add(offense)
                        else:
                            if offense in disarm_thief[defense]:
                                # Failed to injure defender, so not disarm stolen
                                disarm_thief[defense].remove(offense)
                    else:
                        if get_speed(defense) - get_speed(offense) >= 2:
                            if defense not in self.no_escape:
                                self.full_escape.add(defense)
                        else:
                            self.full_escape.discard(defense)
                            self.no_escape.add(defense)

                return priority, self.tic_index, fight

            def debug_tic(priority: int, p: Player):
                self.tic_index += 1

                def debug_print():
                    self._append_to_event_list(self.combat_group_to_events[group],
                                               f"{p.name} ({get_combat(p)}/{get_survivability(p)}) "
                                               f"(S{get_speed(p)}) "
                                               f"{[i.name for i in p.get_items()]}"
                                               f"{[c.name for c in conditions[p]]}"
                                               f"{p.relative_condition_debug()}",
                                               [p])

                return priority, self.tic_index, debug_print

            def escape_message_tic(p: Player, e: Player):
                self.tic_index += 1

                def escape_message():
                    self._append_to_event_list(self.combat_group_to_events[group],
                                               f"{p.name} escaped {e.name}.",
                                               [p, e], info=InfoScope.PUBLIC)

                return -1, self.tic_index, escape_message

            if not self.for_speed:
                self.escape = self.speed_sim()
                for player, escaped in self.escape:
                    if player in group:
                        queue.put(escape_message_tic(player, escaped))

            for player in group:
                combat[player] = 1
                survivability[player] = 1
                conditions[player] = player.conditions[:] + player.turn_conditions[:]

                if player.willpower:
                    conditions[player].append(Condition.HAS_WILLPOWER)

                # Bunker Effect
                bunker_combat_skill = Skill(-1, text="Bunker Combat +1", effect=Effect.COMBAT, value=1, priority=21,
                                            info=InfoScope.HIDDEN, trigger=Trigger.SELF,
                                            self_has_condition=Condition.BUNKERING)
                bunker_survive_skill = Skill(-1, text="Bunker Survive +2", effect=Effect.SURVIVABILITY,
                                             value=2, priority=21,
                                             info=InfoScope.HIDDEN, trigger=Trigger.SELF,
                                             self_has_condition=Condition.BUNKERING)

                queue.put(skill_tic(player, bunker_combat_skill))
                queue.put(skill_tic(player, bunker_survive_skill))
                if not player.distracted:
                    queue.put(skill_tic(player, bunker_combat_skill))
                    queue.put(skill_tic(player, bunker_survive_skill))

                combat[player] += conditions[player].count(Condition.HONED)
                survivability[player] += conditions[player].count(
                    Condition.FORGED)

                if Condition.COMBAT_DOWN in conditions[player]:
                    combat_down_skill = Skill(-1, text="Combat -X", effect=Effect.COMBAT,
                                              value=-1 * conditions[player].count(Condition.COMBAT_DOWN),
                                              priority=69, info=InfoScope.HIDDEN, trigger=Trigger.SELF)
                    queue.put(skill_tic(player, combat_down_skill))

                if Condition.SURVIVABILITY_DOWN in conditions[player]:
                    survivability_down_skill = Skill(-1, text="Survivability -X", effect=Effect.SURVIVABILITY,
                                                     value=-1 * conditions[player].count(Condition.SURVIVABILITY_DOWN),
                                                     priority=69, info=InfoScope.HIDDEN, trigger=Trigger.SELF)
                    queue.put(skill_tic(player, survivability_down_skill))

                if survivability[player] > combat[player]:
                    survivability[player] += conditions[player].count(
                        Condition.IMBALANCE)
                else:
                    combat[player] += conditions[player].count(
                        Condition.IMBALANCE)
                bal = conditions[player].count(Condition.BALANCE)
                while bal:
                    bal -= 1
                    if combat[player] < survivability[player]:
                        combat[player] += 1
                    else:
                        survivability[player] += 1
                if Condition.PETRIFIED in conditions[player]:
                    conditions[player].append(Condition.GAS_IMMUNE)

                if player.circuits:
                    conditions[player].append(Condition.USING_GEO)

                if player.hydro_spells:
                    conditions[player].append(Condition.USING_HYDRO)

                if player.concept:
                    conditions[player].append(Condition.USING_AERO)

                if ABLATIVE in player.items:
                    if player in [_d for _def in self.attacker_to_defenders.values() for _d in _def]:
                        queue.put(skill_tic(player, ABLATIVE_SKILL_A))
                        queue.put(skill_tic(player, ABLATIVE_SKILL_B))
                        player.lose_item(get_item(ABLATIVE))

                for _skill in player.get_skills():
                    # Apply effects from skills to players in order of skill priority
                    if not player.has_condition(Condition.PETRIFIED) or _skill.works_when_petrified:
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

            for (attacker, defender) in simplified_attack_to_defend:
                if attacker in group:
                    queue.put(combat_tic(attacker, defender))
                    queue.put(combat_tic(defender, attacker))

            # Go through the priority queue
            while not queue.empty():
                tic = queue.get()
                if self.for_speed and tic[0] > 179:
                    # Speed Cannot See past priority 179
                    break
                tic[2]()

            if self.for_speed:
                for player, other_set in self.damaged_by.items():
                    if player in group:
                        for other in other_set:
                            speed_dif = get_speed(player) - get_speed(other)
                            if speed_dif > 0:
                                self.escape.add((player, other))

            # Disarm Stealing happens BEFORE Looting corpses
            for (victim, thieves) in disarm_thief.items():
                if thieves:
                    stolen = victim.get_held_weapon()
                    victim.items.remove(stolen.pin)
                    living_thieves = [
                        thief for thief in thieves if thief not in dead_list]
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
                if not player.is_automata:
                    for murderer in self.injured_by.get(player, set()):
                        if murderer not in dead_list and murderer.temperament == Temperament.BLOODTHIRSTY:
                            if player not in self.blood_thirst:
                                self.blood_thirst[player] = set()
                            self.blood_thirst[player].add(murderer)
                loot_items = [item for item in player.get_items() if item.loot]
                # Looting can't happen if there is more than one survivor
                if len(survivors) == 1:
                    looter = survivors[0]
                    for item in loot_items:
                        looter.items.append(item.pin)
                        self._append_to_event_list(self.combat_group_to_events[group],
                                                   f"{looter.name} looted {player.name}'s "
                                                   f"{item.name}.",
                                                   [looter], InfoScope.PRIVATE)
                else:
                    self._append_to_event_list(self.combat_group_to_events[group],
                                               f"{player.name}'s items were lost in the confusion.",
                                               survivors, InfoScope.PRIVATE)

                if player.bounty:
                    bounty = player.bounty
                    player.bounty = 0

                    enemies = []
                    for fighter in survivors:
                        if player in self.attacker_to_defenders.get(fighter, set()) \
                                or fighter in self.attacker_to_defenders.get(player, set()):
                            enemies.append(fighter)
                    if enemies:
                        per_enemy_bounty = bounty // len(enemies)
                        if per_enemy_bounty:
                            credit = "credit"
                            if per_enemy_bounty > 1:
                                credit = "credits"
                            self._append_to_event_list(self.combat_group_to_events[group],
                                                       f"You earned {per_enemy_bounty} "
                                                       f"{credit} for killing {player.name}.",
                                                       enemies, InfoScope.PRIVATE)
                            for bounty_hunter in enemies:
                                bounty_hunter.gain_credits(per_enemy_bounty)

            for player in group:
                if Condition.NO_CONTINGENCY in conditions[player]:
                    self.contingency_locked.add(player)
                if player in self.full_escape:
                    self._append_to_event_list(self.combat_group_to_events[group],
                                               f"{player.name} escaped completely.",
                                               [player], InfoScope.PUBLIC)

    def check_range(self, player, target, ignore_escape=False):
        # Quick little BFS to check if player can reach target using edges, with a small bit of
        # state to make things faster
        if player == target:
            return True

        if not ignore_escape:
            for (escapee, escaper) in self.escape:
                if (escapee, escaper) == (player, target) or (escapee, escaper) == (target, player):
                    return False

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
                              info: InfoScope = InfoScope.PUBLIC,
                              aero: Optional[Player] = None):
        if info == InfoScope.WIDE:
            event_list.append((message, affected, InfoScope.PUBLIC))
            event_list.append((f"Your intuition tells you "
                               f"this has to do with the concept {aero.concept}.",
                               affected, InfoScope.WIDE))
            self.wide_check = True
        elif info == InfoScope.NARROW:
            event_list.append((message, affected, InfoScope.PRIVATE))
            event_list.append((f"Your intuition tells you "
                               f"this has to do with {aero.name}'s Aeromancy ({aero.concept}).",
                               [p for p in affected if p.has_condition(
                                   Condition.INTUITION)],
                               InfoScope.PRIVATE))
        elif info == InfoScope.NARROW_IMPERSONAL:
            event_list.append((message, [p for p in affected if p != aero], InfoScope.PRIVATE))
            event_list.append((f"Your intuition tells you "
                               f"this has to do with {aero.name}'s Aeromancy ({aero.concept}).",
                               [p for p in affected if p.has_condition(
                                   Condition.INTUITION)],
                               InfoScope.PRIVATE))
        elif info == InfoScope.SUBTLE:
            event_list.append((message,
                               [p for p in affected if p.has_condition(
                                   Condition.INTUITION) or p == aero],
                               InfoScope.PRIVATE))
            event_list.append((f"Your intuition tells you "
                               f"this has to do with {aero.name}'s Aeromancy ({aero.concept}).",
                               [p for p in affected if p.has_condition(
                                   Condition.INTUITION)],
                               InfoScope.PRIVATE))
        elif info == InfoScope.SUBTLE_IMPERSONAL:
            event_list.append((message,
                               [p for p in affected if p.has_condition(
                                   Condition.INTUITION)],
                               InfoScope.PRIVATE))
            event_list.append((f"Your intuition tells you "
                               f"this has to do with {aero.name}'s Aeromancy ({aero.concept}).",
                               [p for p in affected if p.has_condition(
                                   Condition.INTUITION)],
                               InfoScope.PRIVATE))

        elif info == InfoScope.BLATANT:
            event_list.append((message, affected, InfoScope.BROADCAST))
            event_list.append((f"Your intuition tells you "
                               f"this has to do with the concept {aero.concept}.",
                               affected, InfoScope.WIDE))
        elif info == InfoScope.UNMISTAKABLE:
            event_list.append((message, affected, InfoScope.BROADCAST))
            event_list.append((f"This unmistakably has to do with "
                               f"{aero.name}'s Aeromancy ({aero.concept}).",
                               affected, InfoScope.BROADCAST))
        else:
            event_list.append((message, affected, info))

        if info in [InfoScope.BROADCAST, InfoScope.BLATANT, InfoScope.UNMISTAKABLE]:
            self.broadcast_events.append((message, False))
            if info == InfoScope.BLATANT:
                self.broadcast_events.append((f"Your intuition tells you this "
                                              f"has to do with the concept {aero.concept}.", True))
            elif info == InfoScope.UNMISTAKABLE:
                self.broadcast_events.append((f"This unmistakably has to do with "
                                              f"{aero.name}'s Aeromancy ({aero.concept}).", False))

    def hot_blood_check(self, player: "Player"):
        return player.name in self.hot_blood

    def blood_thirst_share_count(self, player: "Player"):
        encountered = False
        minimum = 1000
        for dead, killers in self.blood_thirst.items():
            if player in killers:
                encountered = True
                minimum = min(minimum, len(killers))
        if not encountered:
            return 0
        return minimum

    def get_combat_report_for_player(self, player: "Player"):
        report = ""
        for (group, events) in self.combat_group_to_events.items():
            if player in group:
                for other in group:
                    if other in self.attacker_to_defenders:
                        report += other.action.public_description \
                                      .replace("attacked", self.verb_dict.get(other, 'attacked')) + os.linesep
                for event in events:
                    if event[2] == InfoScope.WIDE:
                        if player.has_condition(Condition.INTUITION):
                            report += event[0] + os.linesep
                    elif event[2] in [InfoScope.PUBLIC, InfoScope.BROADCAST] or player in event[1]:
                        report += event[0] + os.linesep
                for other in group:
                    if not self.check_range(player, other, ignore_escape=True):
                        report = report.replace(other.name, "Someone")
        return report

    def get_combat_report_for_player_as_observer(self, player: "Player", observer: "Player"):
        report = ""
        for (group, events) in self.combat_group_to_events.items():
            if player in group:
                for other in group:
                    if other in self.attacker_to_defenders:
                        report += other.action.public_description \
                                      .replace("attacked", self.verb_dict.get(other, 'attacked')) + os.linesep
                for event in events:
                    if event[2] == InfoScope.WIDE:
                        if observer.has_condition(Condition.INTUITION):
                            report += event[0] + os.linesep
                    elif event[2] in [InfoScope.PUBLIC, InfoScope.BROADCAST]:
                        report += event[0] + os.linesep
                for other in group:
                    if not self.check_range(player, other, ignore_escape=True):
                        report = report.replace(other.name, "Someone")
        return report

    def get_public_combat_report(self, intuition=False, ignore_player: Optional['Player'] = None):
        report = ""
        for (group, events) in self.combat_group_to_events.items():
            if not ignore_player or ignore_player not in group or 'Someone' in self.get_combat_report_for_player(
                    ignore_player):
                for player in group:
                    if player in self.attacker_to_defenders:
                        report += player.action.public_description + os.linesep
                for event in events:
                    if event[2] in (InfoScope.PUBLIC, InfoScope.BROADCAST):
                        report += event[0] + os.linesep
                    elif event[2] == InfoScope.WIDE and intuition:
                        report += event[0] + os.linesep
            report += os.linesep
        return report

    def reset(self):
        self.tic_index = 0

        self.broadcast_events = []

        self.hot_blood = set()
        self.blood_thirst = {}
        self.injured_by = {}
        self.report_dict = {}
        self.attacker_to_defenders = {}
        self.combat_group_to_events = {}
        self.verb_dict = {}  # Used if 'attacked' isn't appropriate
        self.range_edges = []  # One directional edges used to calculate range

        self.ambushes = {}  # First populated when attempting to ambush, then pruned

        self.damaged_by = {}  # Used by ambush

        self.drained_by = {}
        self.drainers = set()
        self.drained = set()

        self.solitary_combat = set()

        self.info_once.clear()
        self.speed.clear()

        self.escape.clear()
        self.full_escape.clear()
        self.no_escape.clear()
        self.contingency_locked.clear()

        self.wide_check = False


def get_combat_handler() -> CombatHandler:
    if CombatHandler.REAL_HANDLER is None:
        CombatHandler.REAL_HANDLER = CombatHandler()
        CombatHandler.REAL_HANDLER.is_real = True
    return CombatHandler.REAL_HANDLER
