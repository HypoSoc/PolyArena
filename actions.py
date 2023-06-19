import os
from queue import PriorityQueue
from typing import TYPE_CHECKING, Set, Dict, Optional, Tuple, List, Type, Union

import roman as roman
import random

from ability import Ability, get_ability, get_ability_by_name
from combat import get_combat_handler
from constants import Temperament, Condition, Trigger, Effect, InfoScope, \
    COMBAT_PLACEHOLDER, SELF_PLACEHOLDER, TARGET_PLACEHOLDER, InjuryModifier, Element, AFFLICTIONS, CONDITION_IMMUNITY
from items import get_item_by_name, get_item, Item, Rune
from report import get_main_report

if TYPE_CHECKING:
    from game import Game
    from player import Player
    from automata import Automata
    from skill import Skill

POISON_GAS = get_item_by_name("Poison Gas").pin
SHROOMS = get_item_by_name("Shrooms").pin
MEDKIT = get_item_by_name("Medkit").pin
DEPLETED_MEDKIT = get_item_by_name("1/2 Medkit").pin
LIQUID_MEMORIES = get_item_by_name("Liquid Memories").pin
HEALING_TANK = get_item_by_name("Healing Tank").pin
BOOBY_TRAP = get_item_by_name("Booby Trap").pin
WORKBENCH = get_item_by_name("Workbench").pin
AUTOMATA = get_item_by_name("Automata").pin


QM_ABILITY_PINS = [get_ability_by_name("Divination").pin, get_ability_by_name("Danger Precognition").pin]

# For conditional trading
# Player action target
ACTION_CONDITION = Tuple['Player', Type['Action'], Optional['Player'], bool]  # source, action, target, Positive
# Player, minimum credits, minimum items
ITEM_CONDITION = Tuple['Player', int, Dict['Item', int]]


def noncombat_damage(source: 'Player', victim: 'Player', modifiers: List[InjuryModifier] = None, petrify=False):
    if not modifiers:
        modifiers = []

    if source.has_condition(Condition.PETRIFY) or petrify:
        victim.petrify(long=source.has_condition(Condition.LONG_PETRIFY), mini=InjuryModifier.MINI in modifiers)

    else:
        if source.has_condition(Condition.INFLICT_CAUTERIZE):
            modifiers.append(InjuryModifier.PERMANENT)
        if source.has_condition(Condition.INFLICT_GRIEVOUS):
            modifiers.append(InjuryModifier.GRIEVOUS)

        if victim.has_condition(Condition.GRIEVOUS_IMMUNE):
            if InjuryModifier.GRIEVOUS in modifiers and InjuryModifier.PERMANENT not in modifiers:
                modifiers = [modifier for modifier in modifiers if modifier != InjuryModifier.GRIEVOUS]

        if victim.has_condition(Condition.NONLETHAL_IMMUNE) and InjuryModifier.NONLETHAL in modifiers:
            return

        victim.wound(injury_modifiers=modifiers)


class Action:
    tic_index = 0

    queue = PriorityQueue()
    players: Set['Player'] = set()
    not_wandering: Set['Player'] = set()
    interrupted_players: Set['Player'] = set()
    progress_dict: Dict['Player', int] = {}
    no_class: Set['Player'] = set()  # Used poison gas or attuned
    attacked: Set['Player'] = set()

    # Used for conditional trades based on actions
    action_record: List[ACTION_CONDITION] = []
    spied: Dict["Player", Set["Player"]] = {}
    fake_action_record: List[ACTION_CONDITION] = []
    fake_spied: Dict["Player", Set["Player"]] = {}

    # Used for teaching/learning handshake
    # Teacher: Student
    teacher_student: Dict['Player', 'Player'] = {}
    # Student: Teacher
    student_teacher: Dict['Player', 'Player'] = {}
    # Teacher: Ability
    teacher_ability: Dict['Player', 'Ability'] = {}

    # Used for tattooing handshake
    # Artist: Canvas
    artist_canvas: Dict['Player', 'Player'] = {}
    # Canvas: Artist
    canvas_artist: Dict['Player', 'Player'] = {}
    # Artist: Rune
    artist_rune: Dict['Player', 'Rune'] = {}

    # Used to allow Altruism to work when multiple players heal the same injured player
    was_healed: Set["Player"] = set()

    def __init__(self, priority, game: Optional['Game'], player: Optional["Player"], fragile: bool = True,
                 public_description: str = "", on_interrupt: str = "", combat_on_interrupt: str = ""):
        self.game = game
        self.player = player
        if self.player and game and not game.simulation:
            Action.players.add(self.player)

        self.fragile = fragile
        self.public_description = public_description
        self.on_interrupt = on_interrupt
        self.combat_on_interrupt = combat_on_interrupt
        self.priority = priority
        self.idx = Action.tic_index

        self.maintains_hiding = False

        Action.tic_index += 1

        if self.game and not game.simulation:  # Hack to make fake actions
            # TODO refactor Action Queue to be a part of game, so simulations are permitted
            Action.queue.put(self)

    def act(self):
        self.player.report += os.linesep
        if self.player and self.player.has_condition(Condition.HIDING) and \
                not self.player.has_condition(Condition.FRESH_HIDING):
            if self.game and self.game.is_day() and not self.maintains_hiding:
                self.player.report += "You came out of hiding." + os.linesep
                get_main_report().broadcast(f"{self.player.name} revealed they were not actually dead.")
                self.player.conditions.remove(Condition.HIDING)
                get_main_report().mark_revealed(self.player)

        interrupted = self.player in Action.interrupted_players

        if not interrupted or not self.fragile:
            if self.public_description:
                get_main_report().add_action(self.player, self.public_description,
                                             hidden=self.player in Illusion.handled)
                self.player.report += self.public_description + os.linesep
        if interrupted and self.fragile:
            get_main_report().add_action(self.player, self.on_interrupt, hidden=self.player in Illusion.handled)
            self.player.report += self.on_interrupt + os.linesep
        if not interrupted or not self.fragile:
            self._act()
        Action.not_wandering.add(self.player)
        self.player.report += os.linesep + os.linesep

    def _act(self):
        pass

    def __eq__(self, other: 'Action'):
        return (self.priority, self.idx) == (other.priority, other.idx)

    def __lt__(self, other: 'Action'):
        return (self.priority, self.idx) < (other.priority, other.idx)

    @staticmethod
    def can_act(player: 'Player'):
        if player.is_dead() or Condition.PETRIFIED in player.conditions:
            return False
        return True

    @classmethod
    def run_turn(cls, game: 'Game'):
        NoncombatSkillStep(game)
        TattooStep(game)
        CombatSimStep(game)
        CombatStep(game)
        ProgressStep(game)
        WillpowerStep(game)
        StatusChangeStep(game)

        last_tic = -100

        while not cls.queue.empty():
            tic = cls.queue.get()
            if int(tic.priority) > int(last_tic):
                for player in Action.players:
                    player.report += os.linesep
                last_tic = tic.priority
            if not tic.player or Action.can_act(tic.player) or isinstance(tic, Resurrect) or \
                    (isinstance(tic, HandleSkill) and
                     ((tic.skill.works_when_petrified and not tic.player.is_dead())
                      or (tic.skill.trigger in [Trigger.ACQUISITION, Trigger.START_OF_GAME]))):
                tic.act()
            elif Condition.PETRIFIED in tic.player.conditions:
                get_main_report().add_petrification(tic.player)

    @classmethod
    def progress(cls, player: 'Player', amt: int):
        if player not in cls.progress_dict:
            cls.progress_dict[player] = 0
        cls.progress_dict[player] += amt
        player.report += f"You have gained {amt} Progress" + os.linesep

    @classmethod
    def add_action_record(cls, player: 'Player', action: Type['Action'],
                          target: Optional['Player'] = None, fake=False):
        if fake:
            Action.fake_action_record.append((player, action, target, True))
        else:
            Action.action_record.append((player, action, target, True))

    @classmethod
    def check_action_record(cls, game: 'Game', observer: 'Player', condition: ACTION_CONDITION) -> bool:
        if not game.is_day() and not observer.has_ability("Panopticon"):
            if condition[0] != observer:
                if condition[0] not in Action.spied.get(observer, []):
                    if not condition[2] == observer or condition[1] not in [Teach, Learn, Heal, Attack]:
                        # Can't validate action for condition
                        return not condition[3]

            if condition[0] in Action.fake_spied.get(observer, []):
                for record in Action.fake_action_record:
                    if record[0] == condition[0]:
                        if record[1] == condition[1]:
                            if not condition[2] or record[2] == condition[2]:
                                return condition[3]
                return not condition[3]

        for record in Action.action_record:
            if record[0] == condition[0]:
                if record[1] == condition[1]:
                    if not condition[2] or record[2] == condition[2]:
                        return condition[3]
        return not condition[3]

    @classmethod
    def create_automata(cls, game: 'Game', owner: 'Player', name: 'str'):
        get_main_report().broadcast(f"The Automata {name} was brought into being.")
        if owner.is_automata:
            owner = owner.owner
        import automata
        automata = automata.Automata(name, owner, conditions=[], items=[],
                                     bounty=0, relative_conditions={}, tattoo=None,
                                     game=game)
        Action.not_wandering.add(automata)
        owner.report += f"You acquired {name}." + os.linesep

    @classmethod
    def handle_death_triggers(cls, game: Optional['Game'], dead_player: 'Player'):
        if game and not game.simulation:
            for player in Action.players:
                if not player.is_dead():
                    for skill in player.get_skills():
                        if skill.trigger == Trigger.PLAYER_DIED:
                            HandleSkill(game, player, skill, targets=[dead_player])


class HandleSkill(Action):
    info_once_dict: Dict['Player', Set[str]] = {}
    info_once_broadcast: Set[str] = set()

    def __init__(self, game: Optional['Game'], player: "Player", skill: 'Skill',
                 targets: Optional[List['Player']] = None, fake: bool = False):
        super().__init__(priority=skill.priority, game=game, player=player, fragile=False)
        if targets is None:
            self.targets = [player]
        else:
            self.targets = targets
        self.skill = skill
        self.fake = fake  # Used to disguise that copycat and trade secrets fail vs counter int

    def act(self):
        if self.player.is_dead():
            return

        if self.skill.self_has_condition and not self.player.has_condition(self.skill.self_has_condition):
            return
        if self.skill.self_not_condition and self.player.has_condition(self.skill.self_not_condition):
            return

        if self.skill.fragile and self.player.has_condition(self.skill.fragile):
            return

        def add_to_report(p: 'Player', msg: str, override: bool = False) -> bool:
            if override or self.skill.effect != Effect.INFO_ONCE:
                p.report += get_main_report().face_mask_replacement(msg+os.linesep, p.name)
                return True
            elif msg not in HandleSkill.info_once_dict.get(p, []):
                p.report += get_main_report().face_mask_replacement(msg + os.linesep, p.name)
                if p not in HandleSkill.info_once_dict:
                    HandleSkill.info_once_dict[p] = set()
                HandleSkill.info_once_dict[p].add(msg)
                return True
            return False

        def add_to_broadcast(msg: str, intuition_required: bool = False,
                             force_once: bool = False) -> bool:
            if not force_once and self.skill.effect != Effect.INFO_ONCE:
                get_main_report().broadcast(msg, intuition_required=intuition_required)
                return True
            elif msg not in HandleSkill.info_once_broadcast:
                HandleSkill.info_once_broadcast.add(msg)
                get_main_report().broadcast(msg, intuition_required=intuition_required)
                return True
            return False

        schedule_targets = []

        for original_target in self.targets:
            target = original_target

            if target.is_dead() and not self.skill.trigger == Trigger.PLAYER_DIED:
                continue
            if self.skill.target_has_condition and not target.has_condition(self.skill.target_has_condition):
                continue
            if self.skill.target_not_condition and target.has_condition(self.skill.target_not_condition):
                continue

            if self.skill.text:
                text = self.skill.text.replace(SELF_PLACEHOLDER, self.player.name)\
                    .replace(TARGET_PLACEHOLDER, target.name)

                if self.skill.info in [InfoScope.PRIVATE, InfoScope.PERSONAL]:
                    add_to_report(self.player, text)
                    if target != self.player and self.skill.info != InfoScope.PERSONAL:
                        add_to_report(target, text)
                elif self.skill.info == InfoScope.IMPERSONAL:
                    add_to_report(target, text)
                elif self.skill.info in [InfoScope.NARROW, InfoScope.SUBTLE, InfoScope.SUBTLE_IMPERSONAL]:
                    was_printed = False
                    if target != self.player and self.skill.info != InfoScope.SUBTLE_IMPERSONAL:
                        add_to_report(self.player, text)
                    if target.has_condition(Condition.INTUITION) \
                            or self.skill.info == InfoScope.NARROW \
                            or target == self.player:
                        was_printed = add_to_report(target, text)
                    if target.has_condition(Condition.INTUITION) and target != self.player:
                        assert self.player.concept
                        if was_printed:
                            add_to_report(target,
                                          f"Your intuition tells you this has to do "
                                          f"with {self.player.name}'s Aeromancy ({self.player.concept}).",
                                          override=True)
                elif self.skill.info in [InfoScope.PUBLIC, InfoScope.WIDE]:
                    get_main_report().add_action(self.player, text, aero=self.skill.info == InfoScope.WIDE)
                elif self.skill.info in [InfoScope.BROADCAST, InfoScope.BLATANT, InfoScope.UNMISTAKABLE]:
                    if add_to_broadcast(text, force_once=self.skill.info_once_override):
                        if self.skill.info == InfoScope.BLATANT:
                            get_main_report().broadcast(f"Your intuition tells you this has to do "
                                                        f"with the concept {self.player.concept}.",
                                                        intuition_required=True)
                        elif self.skill.info == InfoScope.UNMISTAKABLE:
                            get_main_report().broadcast(f"This unmistakably has to do with "
                                                        f"{self.player.name}'s Aeromancy ({self.player.concept}).",
                                                        intuition_required=False)

            if self.skill.effect in [Effect.INFO, Effect.INFO_ONCE]:
                continue

            times = 1  # For repeated CONDITION type effects
            if self.skill.value_b and isinstance(self.skill.value_b, int):
                times = self.skill.value_b

            if self.skill.self_override:
                target = self.player

            if self.skill.effect == Effect.CONDITION:
                if not self.fake:
                    if Condition[self.skill.value] not in CONDITION_IMMUNITY \
                            or not target.has_condition(CONDITION_IMMUNITY[Condition[self.skill.value]]):
                        for _ in range(times):
                            target.turn_conditions.append(Condition[self.skill.value])
            elif self.skill.effect == Effect.PERMANENT_CONDITION:
                if not self.fake:
                    if Condition[self.skill.value] not in CONDITION_IMMUNITY \
                            or not target.has_condition(CONDITION_IMMUNITY[Condition[self.skill.value]]):
                        for _ in range(times):
                            target.conditions.append(Condition[self.skill.value])
            elif self.skill.effect == Effect.TENTATIVE_CONDITION:
                if not self.fake:
                    if Condition[self.skill.value] not in CONDITION_IMMUNITY \
                            or not target.has_condition(CONDITION_IMMUNITY[Condition[self.skill.value]]):
                        for _ in range(times):
                            target.tentative_conditions.append(Condition[self.skill.value])
            elif self.skill.effect == Effect.REL_CONDITION:
                # To be refactored if I ever need to give arbitrary players relative_conditions
                if target == self.player:
                    raise Exception("No target for relative condition?")
                if not self.fake:
                    for _ in range(times):
                        self.player.add_relative_condition(target, Condition[self.skill.value])
            elif self.skill.effect == Effect.REMOVE_CONDITION:
                if not self.fake:
                    for _ in range(times):
                        if Condition[self.skill.value] in target.turn_conditions:
                            target.turn_conditions.remove(Condition[self.skill.value])
                        elif Condition[self.skill.value] in target.conditions:
                            target.conditions.remove(Condition[self.skill.value])
            elif self.skill.effect == Effect.DEV_SABOTAGE:
                if target == self.player:
                    raise Exception("No target for dev sabotage?")
                if not self.fake:
                    target.dev_sabotaged(self.skill.text.replace(SELF_PLACEHOLDER, "somebody")
                                         .replace(TARGET_PLACEHOLDER, target.name))
            elif self.skill.effect == Effect.COPYCAT:
                if target == self.player:
                    raise Exception("No target for copycat?")
                self.player.copycat(target, fake=self.fake)
            elif self.skill.effect == Effect.PROGRESS:
                if not self.fake:
                    Action.progress(target, self.skill.value)
            elif self.skill.effect == Effect.MAX_WILLPOWER:
                if not self.fake:
                    target.max_willpower += self.skill.value
            elif self.skill.effect == Effect.DAMAGE:
                if not self.fake:
                    noncombat_damage(self.player, target)
            elif self.skill.effect == Effect.GRIEVOUS:
                if not self.fake:
                    noncombat_damage(self.player, target, [InjuryModifier.GRIEVOUS])
            elif self.skill.effect == Effect.NONLETHAL:
                if not self.fake:
                    noncombat_damage(self.player, target, [InjuryModifier.NONLETHAL])
            elif self.skill.effect == Effect.KILL:
                if not self.fake:
                    target.kill()
            elif self.skill.effect == Effect.PETRIFY:
                if not self.fake:
                    noncombat_damage(self.player, target, petrify=True)
            elif self.skill.effect == Effect.MINI_PETRIFY:
                if not self.fake:
                    noncombat_damage(self.player, target, [InjuryModifier.MINI], petrify=True)
            elif self.skill.effect == Effect.HEAL:
                if not self.fake:
                    target.heal()
            elif self.skill.effect == Effect.ITEM:
                if not self.fake:
                    if self.skill.value_b:
                        target.gain_item(get_item(self.skill.value), self.skill.value_b)
                    else:
                        target.gain_item(get_item(self.skill.value))
            elif self.skill.effect == Effect.CREDITS:
                if not self.fake:
                    if self.skill.value > 0:
                        target.gain_credits(self.skill.value)
                        target.report += f"You gained {self.skill.value} credits. ({target.credits} total)." \
                                         + os.linesep
                    elif self.skill.value < 0:
                        target.lose_credits(self.skill.value * -1)
                        target.report += f"You lost {self.skill.value * -1} credits. ({target.credits} remaining)." \
                                         + os.linesep
            elif self.skill.effect == Effect.ACADEMIC:
                if not self.fake:
                    target.academics += self.skill.value
                    target.report += f"Academics ({target.academics})."
            elif self.skill.effect == Effect.INTERRUPT:
                if not self.fake:
                    Action.interrupted_players.add(target)
            elif self.skill.effect == Effect.SCHEDULE:
                if not self.fake:
                    if self.skill.value_b:
                        schedule_targets.append(target)
                    else:
                        from skill import get_skill
                        HandleSkill.handle_noncombat_skill(self.game, self.player, get_skill(self.skill.value))
            elif self.skill.effect == Effect.GAIN_ABILITY_OR_PROGRESS:
                if not self.fake:
                    ability = get_ability(self.skill.value)
                    if target.has_ability(ability.name, strict=True):
                        target.report += f"You already have {ability.name}.{os.linesep}"
                        Action.progress(target, ability.cost)
                    elif ability.get_prerequisite() and \
                            not target.has_ability(ability.get_prerequisite().name, strict=True,
                                                   ignore_this_turn=False):
                        target.report += f"You lack the prerequisite for {ability.name}.{os.linesep}"
                        Action.progress(target, ability.cost)
                    else:
                        target.gain_ability(ability)

            else:
                raise Exception(f"Unhandled effect type in noncombat! {self.skill.effect.name} {self.skill.text}")

        if self.skill.effect == Effect.SCHEDULE:
            if schedule_targets:
                self.game.add_event_in_x_turns(self.skill.value_b, skill_pin=self.skill.value,
                                               source=self.player, targets=schedule_targets)

    @classmethod
    def handle_noncombat_skill(cls, game: 'Game', player: 'Player', skill: 'Skill'):
        if skill.trigger == Trigger.NONCOMBAT:
            HandleSkill(game, player, skill)
        elif skill.trigger == Trigger.TARGET:
            if skill.targets:
                HandleSkill(game, player, skill, targets=skill.targets)
        elif skill.trigger == Trigger.ALL:
            HandleSkill(game, player, skill, targets=list(Action.players))
        elif skill.trigger == Trigger.RANDOM:
            HandleSkill(game, player, skill, targets=[random.choice([p for p in Action.players if not p.is_dead()])])
        elif skill.trigger == Trigger.RANDOM_OTHER:
            HandleSkill(game, player, skill, targets=[random.choice([p for p in Action.players if not p.is_dead()
                                                                     and p != player])])
        elif skill.trigger == Trigger.OTHERS:
            HandleSkill(game, player, skill, targets=[p for p in Action.players if p != player])


class Wander(Action):
    def __init__(self, game: Optional['Game'], player: "Player"):
        super().__init__(priority=80, game=game, player=player, fragile=True,
                         public_description=f"{player.name} wandered aimlessly.",
                         on_interrupt=f"{player.name} failed to wander aimlessly.")
        self.maintains_hiding = True

    def act(self):
        if self.player not in Action.not_wandering:
            if self.player.has_condition(Condition.HIDING):
                self.public_description = f"{self.player.name} hid."
                self.on_interrupt = f"{self.player.name} failed to hide."
            super().act()

    def _act(self):
        self.player.turn_conditions.append(Condition.WANDERED)


# Universal Actions

# Adds player to combat
class Attack(Action):
    def __init__(self, game: Optional["Game"], player: "Player", target: "Player"):
        super().__init__(priority=30, game=game, player=player, fragile=False,
                         public_description=f"{player.name} attacked {target.name}",
                         combat_on_interrupt=f"while they were attacking {target.name}")
        self.target = target

    def act(self):
        if self.target in MasterIllusion.redirect.get(self.player, {}):
            self.target = MasterIllusion.redirect[self.player][self.target]

        if self.target.is_dead():
            # Player will wander aimlessly
            pass
        else:
            if self.player.has_condition(Condition.HIDING) and \
                    not self.player.has_condition(Condition.FRESH_HIDING):
                if self.game and self.game.is_day():
                    self.player.report += "You came out of hiding." + os.linesep
                    get_main_report().broadcast(f"{self.player.name} revealed they were not actually dead.")
                    self.player.conditions.remove(Condition.HIDING)
                    get_main_report().mark_revealed(self.player)
            if self.target in Illusion.handled:
                if self.target.fake_action.combat_on_interrupt:
                    self.public_description += " " + self.target.fake_action.combat_on_interrupt
            else:
                if self.target.action.combat_on_interrupt:
                    self.public_description += " " + self.target.action.combat_on_interrupt
            self.public_description += "."
            Action.interrupted_players.add(self.target)
            Action.attacked.add(self.target)
            get_combat_handler().add_attack(self.player, self.target)
            if self.target.fake_action.on_interrupt:
                self.target.fake_action.public_description = self.target.fake_action.on_interrupt

            if self.target.has_condition(Condition.HIDING):
                if self.game and self.game.is_day():
                    get_main_report().broadcast(f"{self.target.name} was discovered to be alive.")
                    self.target.conditions.remove(Condition.HIDING)

            # The combat handler will ensure it gets added to the players regular report
            get_main_report().add_action(self.player, self.public_description, hidden=self.player in Illusion.handled)
            Action.not_wandering.add(self.player)
            Action.add_action_record(self.player, Attack, self.target)
            self.player.turn_conditions.append(Condition.ATTACKED)


class Bunker(Action):
    def __init__(self, game: Optional['Game'], player: "Player", bonus: bool):
        super().__init__(priority=20, game=game, player=player, fragile=False,
                         public_description=f"{player.name} bunkered.",
                         combat_on_interrupt="while they were bunkering")
        self.bonus = bonus

    def act(self):
        if self.bonus:
            if not self.player.has_condition(Condition.BONUS_BUNKER):
                return
        super().act()

    def _act(self):
        if self.bonus and self.player.has_condition(Condition.FRAGILE_BUNKER):
            self.player.turn_conditions.append(Condition.FRAGILE_BUNKERING)
        else:
            self.player.turn_conditions.append(Condition.BUNKERING)
        if self.player.temperament == Temperament.PARANOIAC:
            Action.progress(self.player, 2)
        if HEALING_TANK in self.player.items:
            Heal(self.game, self.player, self.player, from_healing_tank=True)
        Action.add_action_record(self.player, Bunker)


class Learn(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player",):
        super().__init__(priority=41, game=game, player=player, fragile=True,
                         public_description="",
                         on_interrupt=f"{player.name} failed to learn from {target.name}.",
                         combat_on_interrupt=f"while they were trying to learn from {target.name}")
        self.target = target

    def _act(self):
        if not Action.can_act(self.target) or self.target not in Action.teacher_student \
                or Action.teacher_student[self.target] != self.player:
            self.player.report += f"{self.player.name} failed to learn from {self.target.name}, " \
                                  f"so {self.player.name} trained instead." + os.linesep
            Train(self.game, self.player)
        else:
            Action.student_teacher[self.player] = self.target
            ability = Action.teacher_ability[self.target]
            get_main_report().add_action(self.player, f"{self.player.name} learned from {self.target.name}.",
                                         hidden=self.player in Illusion.handled)
            self.player.report += f"{self.player.name} learned {ability.name} from {self.target.name}." + os.linesep
            self.player.gain_ability(ability)
            Action.add_action_record(self.player, Learn, self.target)


class Teach(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player", ability: "Ability"):
        super().__init__(priority=40, game=game, player=player, fragile=True,
                         public_description="",
                         on_interrupt=f"{player.name} failed to teach {target.name}.",
                         combat_on_interrupt=f"while they were trying to teach {target.name}")
        self.target = target
        self.ability = ability

    def _act(self):
        if not Action.can_act(self.target) or self.ability in self.target.get_abilities() or \
                (self.ability.get_prerequisite() and
                 self.ability.get_prerequisite() not in self.target.get_abilities()):
            self.player.report += f"{self.player.name} failed to teach {self.target.name}, " \
                                  f"so {self.player.name} trained instead." + os.linesep
            Train(self.game, self.player)
        else:
            Action.teacher_student[self.player] = self.target
            Action.teacher_ability[self.player] = self.ability
            TeachFollow(self.game, self.player, self.target, self.ability)


# Used only by Teach
class TeachFollow(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player", ability: "Ability"):
        super().__init__(priority=42, game=game, player=player, fragile=False,
                         public_description="")
        self.target = target
        self.ability = ability

    def _act(self):
        if Action.student_teacher.get(self.target, None) == self.player:
            get_main_report().add_action(self.player, f"{self.player.name} taught {self.target.name}.",
                                         hidden=self.player in Illusion.handled)
            self.player.report += f"{self.player.name} taught {self.target.name} {self.ability.name}." + os.linesep
            if self.player.temperament == Temperament.ALTRUISTIC:
                Action.progress(self.player, 7)
            Action.add_action_record(self.player, Teach, self.target)
        # Coordination failure
        else:
            self.player.report += f"{self.player.name} failed to teach {self.target.name}, " \
                                  f"so {self.player.name} trained instead."
            Train(self.game, self.player)


class Train(Action):
    def __init__(self, game: Optional['Game'], player: "Player"):
        super().__init__(priority=40, game=game, player=player, fragile=True,
                         public_description=f"{player.name} trained.",
                         on_interrupt=f"{player.name} failed to train.",
                         combat_on_interrupt="while they were trying to train")

    def _act(self):
        Action.progress(self.player, 3)
        Action.add_action_record(self.player, Train)
        if self.player not in Illusion.handled:
            if not self.player.dev_plan:
                get_main_report().set_training(self.player, "nothing")
            else:
                train_ability = get_ability(self.player.dev_plan[0])
                train_name = train_ability.name
                if train_ability.pin >= 700:
                    train_name = 'Concept ' + roman.toRoman((train_ability.pin % 100))
                get_main_report().set_training(self.player, train_name)
        self.player.turn_conditions.append(Condition.TRAINED)


# Day Actions

class Class(Action):
    def __init__(self, game: Optional['Game'], player: "Player"):
        super().__init__(priority=40, game=game, player=player, fragile=True,
                         public_description=f"{player.name} went to class.",
                         on_interrupt=f"{player.name} failed to go to class.",
                         combat_on_interrupt="while they were trying to go to class")

    def act(self):
        if self.player in Action.no_class:
            self.player.report += f"{self.player.name} was kicked out of class for being disruptive." + os.linesep
        else:
            super().act()

    def _act(self):
        self.player.academics += 1 + (self.player.conditions + self.player.turn_conditions).count(Condition.STUDIOUS)
        self.player.report += f"Academics ({self.player.academics})"+os.linesep
        if self.player.temperament == Temperament.SCHOLASTIC:
            Action.progress(self.player, 5)
        Action.add_action_record(self.player, Class)
        self.player.turn_conditions.append(Condition.SCHOOLED)


class Doctor(Action):
    def __init__(self, game: Optional['Game'], player: "Player"):
        super().__init__(priority=50, game=game, player=player, fragile=False,
                         public_description=f"{player.name} went to the doctor.",
                         combat_on_interrupt="while they were going to the doctor")

    def _act(self):
        if Condition.INJURED in self.player.conditions:
            Action.was_healed.add(self.player)
        if self.player.heal():
            self.player.report += f"{self.player.name} was treated, but you remain wounded." + os.linesep
        else:
            self.player.report += f"{self.player.name} is now healthy." + os.linesep
        Action.add_action_record(self.player, Doctor)
        self.player.turn_conditions.append(Condition.DOCTOR)


class Shop(Action):
    def __init__(self, game: Optional['Game'], player: "Player", items: Dict['Item', int],
                 automata_names: Optional[List[str]] = None):
        super().__init__(priority=40, game=game, player=player, fragile=True,
                         public_description=f"{player.name} shopped.",
                         on_interrupt=f"{player.name} failed to shop.",
                         combat_on_interrupt="while they were trying to shop")
        self.items = items
        self.automata_names = automata_names
        if not self.automata_names:
            self.automata_names = []

    def act(self):
        if Shop.get_total_cost(self.items) > self.player.get_credits():
            self.player.report += f"{self.player.name} was kicked out of shop club for not having enough credits." \
                                  + os.linesep
        else:
            super().act()

    def _act(self):
        total_cost = Shop.get_total_cost(self.items)
        self.player.lose_credits(total_cost)
        self.player.report += f"{self.player.name} spent {total_cost} credits " \
                              f"({self.player.get_credits()} remaining)." + os.linesep
        for item, amount in self.items.items():
            if item.pin == AUTOMATA:
                assert len(self.automata_names) >= amount
                for i in range(amount):
                    Action.create_automata(self.game, self.player, self.automata_names[i])
            else:
                self.player.gain_item(item, amount)
        Action.add_action_record(self.player, Shop)
        pruned_items = {k: v for k, v in self.items.items() if k.pin != AUTOMATA}
        get_main_report().add_shop(self.player, total_cost, pruned_items, self.automata_names)
        self.player.turn_conditions.append(Condition.SHOPPED)

    @staticmethod
    def get_total_cost(items: Dict['Item', int]):
        running_cost = 0
        for item, amount in items.items():
            running_cost += (item.cost * amount)
        return running_cost


# Skill Restricted Actions

class Heal(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player",
                 is_bonus: bool = False, from_healing_tank: bool = False):
        self.target = target
        self.self_heal = (target == player)
        self.is_bonus = is_bonus
        self.from_healing_tank = from_healing_tank
        if self.self_heal:
            super().__init__(priority=50, game=game, player=player, fragile=False,
                             public_description=f"{player.name} healed themself.",
                             combat_on_interrupt=f"while they were trying to heal themself")
        else:
            super().__init__(priority=50, game=game, player=player, fragile=True,
                             public_description=f"{player.name} went to heal {target.name}",
                             on_interrupt=f"{player.name} failed to heal {target.name}",
                             combat_on_interrupt=f"while they were trying to heal {target.name}")
        if self.from_healing_tank:
            self.public_description = ""
            self.combat_on_interrupt = ""

    def act(self):
        if self.is_bonus and not self.player.has_condition(Condition.BONUS_HEALER):
            self.player.report += "You were unable to heal yourself." + os.linesep
            return  # Player cannot bonus heal
        if not self.from_healing_tank and not self.player.has_condition(Condition.HEALER):
            self.player.report += "You were unable to heal yourself." + os.linesep
            return  # Player cannot heal
        if not self.self_heal:
            if self.target.action.combat_on_interrupt:
                self.public_description += " " + self.target.action.combat_on_interrupt
            self.public_description += "."
        super().act()

    def _act(self):
        if self.self_heal:
            if self.from_healing_tank:
                self.player.report += f"{self.player.name} used a Healing Tank." + os.linesep
            if Condition.INJURED in self.player.conditions:
                Action.was_healed.add(self.player)
            if self.player.heal():
                self.player.report += f"{self.player.name} was treated, but {self.player.name} " \
                                      f"remain wounded." + os.linesep
            else:
                self.player.report += f"{self.player.name} is now healthy." + os.linesep
            Action.add_action_record(self.player, Heal, self.target)
        else:
            if self.target.is_dead():
                self.player.report += f"{self.player.name} could not treat {self.target.name} " \
                                      f"because they are dead." + os.linesep
            else:
                def add_to_player_report(msg: str):
                    self.player.report += get_main_report().face_mask_replacement(msg,
                                                                                  self.player.name)

                def add_to_target_report(msg: str):
                    self.target.report += get_main_report().face_mask_replacement(msg,
                                                                                  self.target.name)
                was_injured = self.target.has_condition(Condition.INJURED)
                if was_injured:
                    Action.was_healed.add(self.target)
                if self.target.has_condition(Condition.PETRIFIED):
                    add_to_player_report(f"{self.player.name} tried to treat {self.target.name}, "
                                         f"but they were a statue." + os.linesep)
                    add_to_target_report(f"{self.player.name} tried to treat {self.target.name}, "
                                         f"but {self.target.name} were a statue." + os.linesep)
                else:
                    if self.target.heal():
                        add_to_player_report(f"{self.player.name} treated {self.target.name}, "
                                             f"but they remain wounded." + os.linesep)
                        add_to_target_report(f"{self.player.name} treated {self.target.name}, "
                                             f"but {self.target.name} remain wounded." + os.linesep)
                    else:
                        add_to_player_report(f"{self.player.name} treated {self.target.name} "
                                             f"and they are now healthy." + os.linesep)
                        add_to_target_report(f"{self.player.name} treated {self.target.name} "
                                             f"and {self.target.name} is now healthy." + os.linesep)
                    if self.player.temperament == Temperament.ALTRUISTIC:
                        if was_injured or self.target in Action.was_healed:
                            Action.progress(self.player, 7)
                        else:
                            add_to_player_report(f"{self.target.name} did not require treatment." + os.linesep)
                Action.add_action_record(self.player, Heal, self.target)


class Steal(Action):
    victim_to_thieves: Dict['Player', Set['Player']] = {}

    def __init__(self, game: Optional['Game'], player: "Player", target: "Player"):
        super().__init__(priority=60, game=game, player=player, fragile=True,
                         public_description=f"{player.name} robbed {target.name}.",
                         on_interrupt=f"{player.name} failed to rob {target.name}.",
                         combat_on_interrupt=f"while they were trying to rob {target.name}")
        self.target = target

    def act(self):
        if not self.player.has_condition(Condition.THIEF):
            return  # Player cannot steal
        super().act()

    def _act(self):
        if self.target.has_condition(Condition.THEFT_AWARE):
            if self.target.get_awareness() > self.player.get_awareness():
                self.player.report += f"You failed to rob {self.target.name}." + os.linesep
                return
        if self.target not in Steal.victim_to_thieves:
            Steal.victim_to_thieves[self.target] = set()
        Steal.victim_to_thieves[self.target].add(self.player)
        trap = False
        items = {}
        for item in self.target.get_items():
            if item.pin == BOOBY_TRAP:
                trap = True
            elif item.loot:
                if item.pin not in items:
                    items[item.pin] = 0
                items[item.pin] += 1
        items = {get_item(pin): amount for pin, amount in items.items()}
        StealFollow(self.game, self.player, self.target, items, trap)


class StealFollow(Action):
    handled: Set['Player'] = set()

    def __init__(self, game: Optional['Game'], player: "Player", target: "Player",
                 items: Dict['Item', int], trap: bool):
        super().__init__(priority=61, game=game, player=player, fragile=False)
        self.target = target
        self.items = items
        self.trap = trap

    def _act(self):
        if len(Steal.victim_to_thieves[self.target]) > 1:
            involved = " and ".join(sorted([get_main_report().face_mask_replacement(player.name, self.player.name)
                                            for player in Steal.victim_to_thieves[self.target]]))
            self.player.report += f"{involved} fought over the loot." + os.linesep
            self.player.report += "It was all lost." + os.linesep

        else:
            if self.items:
                for item, amount in self.items.items():
                    self.player.gain_item(item, amount)
            else:
                self.player.report += "There was nothing to steal..." + os.linesep

        if self.trap:
            self.player.report += "A booby trap exploded in your face!" + os.linesep
            noncombat_damage(self.target, self.player, [InjuryModifier.NONLETHAL])
            get_main_report().broadcast(f"A booby trap exploded in {self.player.name}'s face!")

        if self.target not in StealFollow.handled:
            StealFollow.handled.add(self.target)
            self.target.report += os.linesep + "Somebody robbed you!" + os.linesep
            for item, amount in self.items.items():
                self.target.lose_item(item, amount)
            self.target.destroy_fragile_items()
            self.target.report += os.linesep


class Craft(Action):
    def __init__(self, game: Optional['Game'], player: "Player", items: Dict['Item', int],
                 is_bonus: bool = False, automata_names: Optional[List[str]] = None):
        super().__init__(priority=40, game=game, player=player, fragile=True,
                         public_description=f"{player.name} crafted.",
                         on_interrupt=f"{player.name} failed to craft.",
                         combat_on_interrupt=f"while they were trying to craft something")
        self.items = items
        self.is_bonus = is_bonus
        if not automata_names:
            self.automata_names = []
        else:
            self.automata_names = automata_names

    def act(self):
        if not self.items:
            return

        amt = sum(self.items.values())
        price = sum([abs(item.cost) * amount for (item, amount) in self.items.items()])
        only_shop_items = True
        for item in self.items:
            if item.cost < 0:
                only_shop_items = False

        rune_crafting = False
        for item in self.items:
            if isinstance(item, Rune):
                rune_crafting = True
                if not item.is_simple_rune() and not self.player.has_ability("Rune Crafting II"):
                    self.player.report += f"{item.name} is too complicated for you to craft." + os.linesep
                    return
                if not self.player.has_ability("Rune Crafting I") and not self.player.has_ability("Rune Crafting II"):
                    self.player.report += f"You don't know how to make runes." + os.linesep
                    return

                if not self.player.has_ability(item.get_ability_name(), strict=True):
                    self.player.report += f"You don't have the ability to make a rune " \
                                          f"for {item.get_ability_name()}." + os.linesep
                    return

        if rune_crafting and amt > 1:
            # Can only craft 1 rune at a time, if crafting ANY runes.
            return

        if self.is_bonus and rune_crafting:
            if not self.player.has_ability("Rune Crafting II"):
                return  # Player cannot bonus rune craft

        if not rune_crafting:
            legal_craft = False

            if self.player.has_condition(Condition.LOW_CRAFTING):
                if amt == 1 and price <= 2 and only_shop_items:
                    legal_craft = True

            if self.player.has_condition(Condition.CRAFTING):
                if price <= 3 and only_shop_items:
                    legal_craft = True

            if self.player.has_condition(Condition.HIGH_CRAFTING):
                if price <= 5 and only_shop_items:
                    illegal_items = False
                    for item in self.items:
                        if item.pin in [LIQUID_MEMORIES]:
                            illegal_items = True
                    if not illegal_items:
                        legal_craft = True

            if not legal_craft:
                self.player.report += f"You were unable to craft your items." + os.linesep
                return

        super().act()

    def _act(self):
        for item, amount in self.items.items():
            if item.pin == AUTOMATA:
                assert len(self.automata_names) >= amount
                for i in range(amount):
                    Action.create_automata(self.game, self.player, self.automata_names[i])
            else:
                self.player.gain_item(item, amount)
            if item.pin not in self.player.crafted_before:
                self.player.crafted_before.append(item.pin)
                if self.player.temperament == Temperament.PARANOIAC:
                    Action.progress(self.player, 2)
        Action.add_action_record(self.player, Craft)


class AutomataCraft(Action):
    def __init__(self, game: Optional['Game'], automata: "Automata", items: Dict['Item', int],
                 automata_names: Optional[List[str]] = None):
        assert automata.is_automata
        super().__init__(priority=40, game=game, player=automata, fragile=True,
                         public_description=f"{automata.name} crafted.",
                         on_interrupt=f"{automata.name} failed to craft.",
                         combat_on_interrupt=f"while they were trying to craft something")
        self.items = items
        self.owner = automata.owner
        if not automata_names:
            self.automata_names = []
        else:
            self.automata_names = automata_names

    def act(self):
        if not self.items:
            return

        amt = sum(self.items.values())
        price = sum([abs(item.cost) * amount for (item, amount) in self.items.items()])
        only_shop_items = True
        for item in self.items:
            if item.cost < 0:
                only_shop_items = False

        rune_crafting = False
        for item in self.items:
            if isinstance(item, Rune):
                rune_crafting = True
                if not item.is_simple_rune() and not self.owner.has_ability("Rune Crafting II"):
                    self.owner.report += f"{item.name} is too complicated for your automata to craft." + os.linesep
                    return
                if not self.owner.has_ability("Rune Crafting I") and not self.owner.has_ability("Rune Crafting II"):
                    self.owner.report += f"Your automata does not know how to make runes." + os.linesep
                    return

                if not self.owner.has_ability(item.get_ability_name(), strict=True):
                    self.owner.report += f"Your automata does not have the ability to make a rune " \
                                         f"for {item.get_ability_name()}." + os.linesep
                    return

        if rune_crafting and amt > 1:
            # Can only craft 1 rune at a time, if crafting ANY runes.
            return

        if not rune_crafting:
            legal_craft = False

            if self.owner.has_ability("Crafting I"):
                if amt == 1 and price <= 2 and only_shop_items:
                    legal_craft = True

            if self.owner.has_ability("Crafting II"):
                if price <= 3 and only_shop_items:
                    legal_craft = True

            if self.owner.has_ability("Crafting III"):
                if price <= 5 and only_shop_items:
                    illegal_items = False
                    for item in self.items:
                        if item.pin in [LIQUID_MEMORIES]:
                            illegal_items = True
                    if not illegal_items:
                        legal_craft = True

            if not legal_craft:
                self.player.report += f"Your automata was unable to craft your items." + os.linesep
                return

        super().act()

    def _act(self):
        for item, amount in self.items.items():
            if item.pin == AUTOMATA:
                assert len(self.automata_names) >= amount
                for i in range(amount):
                    Action.create_automata(self.game, self.player, self.automata_names[i])
            else:
                self.player.gain_item(item, amount)
        Action.add_action_record(self.player, Craft)


class Canvas(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player"):
        super().__init__(priority=41, game=game, player=player, fragile=True,
                         public_description="",
                         on_interrupt=f"{player.name} failed get a tattoo from {target.name}.",
                         combat_on_interrupt=f"while they were trying to get a tattoo from {target.name}")
        self.target = target

    def _act(self):
        if not Action.can_act(self.target) or self.target not in Action.artist_canvas \
                or Action.artist_canvas[self.target] != self.player or self.player.tattoo:
            if self.player.tattoo:
                self.player.report += "You already have a tattoo." + os.linesep
            self.player.report += f"{self.player.name} failed to get a tattoo from {self.target.name}, " \
                                  f"so {self.player.name} trained instead." + os.linesep
            Train(self.game, self.player)
        else:
            Action.canvas_artist[self.player] = self.target
            rune = Action.artist_rune[self.target]
            get_main_report().add_action(self.player, f"{self.player.name} got tattooed by {self.target.name}.",
                                         hidden=self.player in Illusion.handled)
            self.player.report += f"{self.player.name} got tattooed by {self.target.name} " \
                                  f"with {rune.get_ability_name()}." + os.linesep
            self.player.tattoo = rune.pin
            Action.add_action_record(self.player, Canvas, self.target)


class Tattoo(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player", rune: "Rune"):
        if player == target:
            super().__init__(priority=40, game=game, player=player, fragile=True,
                             public_description=f"{player.name} tattooed themself.",
                             on_interrupt=f"{player.name} failed to tattoo themself.",
                             combat_on_interrupt=f"while they were trying to tattoo themself")
            self.self_target = True
        else:
            super().__init__(priority=40, game=game, player=player, fragile=True,
                             public_description="",
                             on_interrupt=f"{player.name} failed to tattoo {target.name}.",
                             combat_on_interrupt=f"while they were trying to tattoo {target.name}")
            self.self_target = False
        self.target = target
        self.rune = rune

        self.ability_source = player
        if player.is_automata:
            self.ability_source = player.owner

    def act(self):
        if self.self_target:
            if self.player.tattoo:
                self.player.report += "You already have a tattoo." + os.linesep
                return
        if not self.ability_source.has_ability("Runic Tattoos"):
            return
        super().act()

    def _act(self):
        able_to_tattoo = self.ability_source.has_ability("Runic Tattoos")
        if not self.ability_source.has_ability("Rune Crafting I") and \
                not self.ability_source.has_ability("Rune Crafting II"):
            able_to_tattoo = False
        if not self.rune.is_simple_rune() and not self.ability_source.has_ability("Rune Crafting II"):
            able_to_tattoo = False
        if not self.ability_source.has_ability(self.rune.get_ability_name(), strict=True):
            able_to_tattoo = False

        if not able_to_tattoo:
            self.player.report += f"You were incapable of making the {self.rune.name} Tattoo." + os.linesep
            if self.player.is_automata:
                self.ability_source.report += f"Your automata was incapable " \
                                              f"of making the {self.rune.name} Tattoo." + os.linesep

        if self.self_target:
            if able_to_tattoo:
                self.player.report += f"You tattooed yourself " \
                                      f"with {self.rune.get_ability_name()}." + os.linesep
                self.player.tattoo = self.rune.pin
                Action.add_action_record(self.player, Tattoo, self.player)
        else:
            if not Action.can_act(self.target) or not able_to_tattoo or self.target.tattoo:
                if self.target.tattoo:
                    self.player.report += f"{self.target.name} already has a tattoo." + os.linesep
                self.player.report += f"{self.player.name} failed to tattoo {self.target.name}, " \
                                      f"so {self.player.name} trained instead." + os.linesep
                Train(self.game, self.player)
            else:
                Action.artist_canvas[self.player] = self.target
                Action.artist_rune[self.player] = self.rune
                TattooFollow(self.game, self.player, self.target, self.rune)


# Used only by Tattoo
class TattooFollow(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player", rune: "Rune"):
        super().__init__(priority=42, game=game, player=player, fragile=False,
                         public_description="")
        self.target = target
        self.rune = rune

    def _act(self):
        if Action.canvas_artist.get(self.target) == self.player:
            get_main_report().add_action(self.player, f"{self.player.name} tattooed {self.target.name}.",
                                         hidden=self.player in Illusion.handled)
            self.player.report += f"{self.player.name} tattooed {self.target.name} " \
                                  f"with {self.rune.name}." + os.linesep
            if self.player.temperament == Temperament.ALTRUISTIC:
                Action.progress(self.player, 7)
            Action.add_action_record(self.player, Tattoo, self.target)
        # Coordination failure
        else:
            self.player.report += f"{self.player.name} failed to tattoo {self.target.name}, " \
                                  f"so {self.player.name} trained instead."
            Train(self.game, self.player)


class MultiAttack(Action):
    def __init__(self, game: "Game", player: "Player", targets: List["Player"]):
        self.targets = [target for target in targets if not target.is_dead()]
        target_names = " and ".join([target.name for target in self.targets])

        super().__init__(priority=30, game=game, player=player, fragile=False,
                         public_description=f"{player.name} attacked ",
                         combat_on_interrupt=f"while they were attacking {target_names}")

    def act(self):
        if not self.player.has_condition(Condition.MULTI_ATTACK) or len(self.targets) > 3:
            return

        if self.player and self.player.has_condition(Condition.HIDING) and \
                not self.player.has_condition(Condition.FRESH_HIDING):
            if self.game and self.game.is_day() and not isinstance(self, Wander):
                self.player.report += "You came out of hiding." + os.linesep
                get_main_report().broadcast(f"{self.player.name} revealed they were not actually dead.")
                self.player.conditions.remove(Condition.HIDING)
                get_main_report().mark_revealed(self.player)

        interruption_strings = []
        attacked_someone = False

        if self.player in MasterIllusion.redirect:
            self.targets = [MasterIllusion.redirect[self.player].get(target, target) for target in self.targets]
            self.targets = list(set(self.targets))

        for target in self.targets:
            if target.is_dead():
                pass
            else:
                attacked_someone = True
                if target.action.combat_on_interrupt:
                    interruption_strings.append(f"{target.name} ({target.action.combat_on_interrupt}),")
                else:
                    interruption_strings.append(f"{target.name},")
                Action.interrupted_players.add(target)
                get_combat_handler().add_attack(self.player, target)
                if target.fake_action.on_interrupt:
                    target.fake_action.public_description = target.fake_action.on_interrupt

                if target.has_condition(Condition.HIDING):
                    if self.game and self.game.is_day():
                        get_main_report().broadcast(f"{target.name} was discovered to be alive.")
                        target.conditions.remove(Condition.HIDING)

                Action.add_action_record(self.player, Attack, target)
        if attacked_someone:
            self.public_description += (" and ".join(interruption_strings))[:-1]
            self.public_description += "."

            get_main_report().add_action(self.player, self.public_description, hidden=self.player in Illusion.handled)
            Action.not_wandering.add(self.player)
            self.player.turn_conditions.append(Condition.ATTACKED)


# Bonus Actions

class Spy(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player"):
        super().__init__(priority=85, game=game, player=player, fragile=False,
                         public_description=f"{player.name} spied on {target.name}.")
        self.target = target

    def act(self):
        if not self.player.has_condition(Condition.CAN_SPY):
            return
        if self.game.is_day() and not self.player.has_condition(Condition.DAY_SPY):
            return
        super().act()

    def _act(self):
        counter_int = self.target.has_condition(Condition.COUNTER_INT)
        if counter_int:
            if self.player.has_condition(Condition.PIERCE_COUNTER_INT)\
                    and not self.target.has_condition(Condition.SUPER_COUNTER_INT):
                counter_int = False

        if not counter_int and self.target.has_condition(Condition.SPY_AWARE):
            if self.target.get_awareness() > self.player.get_awareness():
                self.player.report += f"You failed to spy on {self.target.name}." + os.linesep
                for skill in self.target.get_skills():
                    if skill.trigger == Trigger.SPIED_ON:
                        HandleSkill(self.game, self.target, skill, self.player)
                return
        self.player.report += get_main_report().get_spy_report(self.player, self.target, counter_int) + os.linesep
        if self.player not in Action.spied:
            Action.spied[self.player] = set()
        Action.spied[self.player].add(self.target)

        if counter_int:
            Action.add_action_record(player=self.target, action=type(self.target.fake_action),
                                     target=getattr(self.target.fake_action, 'target', None),
                                     fake=True)
            if self.player not in Action.fake_spied:
                Action.fake_spied[self.player] = set()
            Action.fake_spied[self.player].add(self.target)

        for skill in self.player.get_skills():
            if skill.trigger == Trigger.SPY:
                HandleSkill(self.game, self.player, skill, [self.target], fake=counter_int)

        for skill in self.target.get_skills():
            if skill.trigger == Trigger.SPIED_ON:
                HandleSkill(self.game, self.target, skill, [self.player])


# Free Actions

class ConsumeItem(Action):
    unique_pair: Set[Tuple['Player', 'Item']] = set()

    def __init__(self, game: Optional['Game'], player: "Player", item: "Item"):
        if (player, item) in ConsumeItem.unique_pair:
            raise Exception(f"{player.name} is trying to consume multiple copies of the same item ({item.name}).")
        super().__init__(priority=10, game=game, player=player, fragile=False,
                         public_description=f"{player.name} used {item.name}")
        self.item = item
        ConsumeItem.unique_pair.add((player, item))

    def act(self):
        if self.item.pin == self.player.tattoo:
            return
        if self.item.pin in self.player.items:
            self.player.consumed_items.add(self.item.pin)
            self.player.items.remove(self.item.pin)
            self.player.report += f"{self.player.name} used {self.item.name} " \
                                  f"({self.player.items.count(self.item.pin)} remaining)." + os.linesep
            for skill in self.item.get_skills(targets=self.player.item_targets.get(self.item.pin, None)):
                HandleSkill.handle_noncombat_skill(self.game, self.player, skill)
            if self.item.pin == POISON_GAS:
                Action.no_class.add(self.player)
                get_combat_handler().add_solitary_combat(self.player)
            elif self.item.pin == SHROOMS:
                Action.progress(self.player, 3)
            elif self.item.pin == LIQUID_MEMORIES:
                self.player.academics += 1
                self.player.report += f"Academics ({self.player.academics})" + os.linesep

            if isinstance(self.item, Rune):
                if self.item.is_disruptive():
                    if not self.player.has_ability("Quiet Attune"):
                        Action.no_class.add(self.player)
                self.player.temporary_abilities.append(self.item.get_ability_pin())

            if self.player.has_condition(Condition.EFFICIENT_HEALER):
                if self.item.pin == MEDKIT:
                    self.player.gain_item(get_item(DEPLETED_MEDKIT))

        else:
            self.player.report += f"{self.player.name} tried to use {self.item.name}, but it was gone." + os.linesep


class Trade(Action):
    unique_pair: Set[Tuple['Player', 'Player']] = set()

    # {(Sender, Recipient): (Credits, {Item: Amount})}
    item_conditions: Dict[Tuple['Player', 'Player'], Tuple[int, Dict['Item', int]]] = {}

    # Used to prevent a player from promising the same items/credits to multiple players
    reserved: Dict['Player', Tuple[int, Dict['Item', int], List[str]]] = {}

    def __init__(self, game: Optional['Game'], player: "Player", target: "Player",
                 items: Optional[Dict['Item', int]] = None, money: int = 0,
                 automata: Optional[List[Union['Automata', str]]] = None,
                 action_condition: Optional[ACTION_CONDITION] = None,
                 item_condition: Optional[ITEM_CONDITION] = None):
        if (player, target) in Trade.unique_pair:
            raise Exception(f"{player.name} is trying to trade with {target.name} multiple times")
        if money < 0:
            raise Exception(f"{player.name} is trying to give away negative money.")
        if not money and not items and not automata:
            raise Exception(f"{player.name} is trying to place an empty trade.")
        if items is None:
            items = {}
        if automata is None:
            automata = []

        if automata and target.is_automata:
            raise Exception(f"{player.name} is trying to give and automata to an automata.")

        for automaton in automata:
            if not isinstance(automaton, str) and automaton.owner != player:
                raise Exception(f"{player.name} is trying to trade an automata they don't own {automaton.name}.")

        super().__init__(100, game=game, player=player, fragile=False)
        self.target = target
        self.items = items
        self.credits = money
        self.automata = automata
        self.action_condition = action_condition
        self.item_condition = item_condition
        Trade.unique_pair.add((player, target))

    def act(self):
        if self.action_condition:
            if not Action.check_action_record(self.game, self.player, self.action_condition):
                if self.action_condition[3]:
                    self.player.report += f"You did not trade with {self.target.name} " \
                                          f"because the required action did not happen." + os.linesep
                else:
                    self.player.report += f"You did not trade with {self.target.name} " \
                                          f"because the forbidden action occurred." + os.linesep
                return
        failed_trade = False
        reserved_credits, reserved_items, reserved_automata_names = Trade.reserved.get(self.player, (0, {}, []))
        if self.credits:
            reserved_credits += self.credits
            if self.player.get_credits() < reserved_credits:
                self.player.report += f"You do not have enough credits to trade with {self.target.name}." + os.linesep
                failed_trade = True
        if self.items:
            for (item, amount) in self.items.items():
                if item not in reserved_items:
                    reserved_items[item] = 0
                reserved_items[item] += amount
                if self.player.items.count(item.pin) < reserved_items[item]:
                    self.player.report += f"You do not have enough {item.name} to trade with {self.target.name}." \
                                          + os.linesep
                    failed_trade = True
        if self.automata:
            parsed_automata = []  # used so that automata can be traded the same turn they are made
            for automaton in self.automata:
                if isinstance(automaton, str):
                    if automaton not in self.player.automata_registry:
                        self.player.report += f"You do not have an automaton named {automaton}" \
                                              f" so you cannot trade with {self.target.name}." \
                                              + os.linesep
                        failed_trade = True
                    else:
                        parsed_automata.append(self.player.automata_registry[automaton])
                else:
                    parsed_automata.append(automaton)
            self.automata = parsed_automata
            for automaton in self.automata:
                if automaton.name in reserved_automata_names:
                    self.player.report += f"You are only have a single {automaton.name} so you cannot" \
                                          f" trade with {self.target.name}." \
                                          + os.linesep
                    failed_trade = True
                reserved_automata_names.append(automaton.name)
        Trade.reserved[self.player] = (reserved_credits, reserved_items, reserved_automata_names)
        if failed_trade:
            return
        items_and_automata = self.items.copy()
        if self.automata:
            items_and_automata[get_item_by_name("Automata")] = len(self.automata)
        Trade.item_conditions[(self.player, self.target)] = (self.credits, items_and_automata)
        TradeFollow(self.game, self.player, self.target,
                    self.items, self.credits, self.automata,
                    self.item_condition)


# Used only by Trade
class TradeFollow(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player",
                 items: Optional[Dict['Item', int]], money: int,
                 automata: List['Automata'],
                 item_condition: Optional[ITEM_CONDITION]):
        super().__init__(101, game=game, player=player, fragile=False)
        self.target = target
        self.items = items
        self.credits = money
        self.automata = automata
        self.item_condition = item_condition

    def _act(self):
        if self.item_condition:
            pending_credits, pending_items = Trade.item_conditions.get((self.item_condition[0], self.player), (0, {}))
            if pending_credits < self.item_condition[1]:
                self.player.report += f"You did not trade with {self.target.name} because " \
                                      f"{self.item_condition[0].name} did not send you enough credits." + os.linesep
                Trade.item_conditions[(self.player, self.target)] = (0, {})
                return
            for (item, amount) in self.item_condition[2].items():
                if item not in pending_items or pending_items[item] < amount:
                    self.player.report += f"You did not trade with {self.target.name} because " \
                                          f"{self.item_condition[0].name} did not send you enough {item.name}." \
                                          + os.linesep
                    Trade.item_conditions[(self.player, self.target)] = (0, {})
                    return
        TradeFinal(self.game, self.player, self.target, self.items, self.credits, self.automata, self.item_condition)


# Used only by Trade
class TradeFinal(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player",
                 items: Optional[Dict['Item', int]], money: int,
                 automata: List['Automata'],
                 item_condition: Optional[ITEM_CONDITION]):
        super().__init__(102, game=game, player=player, fragile=False)
        self.target = target
        self.items = items
        self.credits = money
        self.automata = automata
        self.item_condition = item_condition

    def _act(self):
        if self.item_condition:
            pending_credits, pending_items = Trade.item_conditions.get((self.item_condition[0], self.player), (0, {}))
            if pending_credits < self.item_condition[1]:
                self.player.report += f"You did not trade with {self.target.name} because " \
                                      f"{self.item_condition[0].name} did not send you enough credits." + os.linesep
                Trade.item_conditions[(self.player, self.target)] = (0, {})
                return
            for (item, amount) in self.item_condition[2].items():
                if item not in pending_items or pending_items[item] < amount:
                    self.player.report += f"You did not trade with {self.target.name} because " \
                                          f"{self.item_condition[0].name} did not send you enough {item.name}." \
                                          + os.linesep
                    Trade.item_conditions[(self.player, self.target)] = (0, {})
                    return
        if self.credits:
            self.player.lose_credits(self.credits)
            self.player.report += f"You sent {self.target.name} {self.credits} credits " \
                                  f"({self.player.get_credits()} remaining)." \
                                  + os.linesep
            self.target.gain_credits(self.credits)
            self.target.report += f"{self.player.name} sent you {self.credits} credits " \
                                  f"({self.target.get_credits()} total)." \
                                  + os.linesep
        if self.items:
            self.player.report += f"You sent {self.target.name} items." + os.linesep
            self.target.report += f"{self.player.name} sent you items." + os.linesep
            for item, amount in self.items.items():
                self.player.lose_item(item, amount)
                self.target.gain_item(item, amount)
        for automaton in self.automata:
            self.player.report += f"You transferred control of {automaton.name} to {self.target.name}." + os.linesep
            self.target.report += f"{self.player.name} gave you control over {automaton.name}." + os.linesep
            automaton.owner = self.target
        get_main_report().add_trade(self.player, self.target, self.credits, self.items, self.automata)


class PlaceBounty(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player", amount: int):
        assert amount > 0
        super().__init__(priority=110, game=game, player=player, fragile=False,
                         public_description="")
        self.target = target
        self.amount = amount
        self.maintains_hiding = True

    def act(self):
        self.player.report += os.linesep
        if self.target.is_dead() or self.target.has_condition(Condition.HIDING):
            self.player.report += f"You cannot place a bounty on {self.target.name} " \
                                  f"because they are dead." + os.linesep + os.linesep
            return
        if self.player.get_credits() < self.amount:
            self.player.report += f"You cannot place a {self.amount} credit bounty on {self.target.name} " \
                                  f"because you don't have enough credits." + os.linesep + os.linesep
            return
        self.player.lose_credits(self.amount)
        self.target.bounty += self.amount
        self.player.report += f"You placed a {self.amount} credit bounty on {self.target.name} " \
                              f"({self.player.get_credits()} credits remain)" + os.linesep + os.linesep
        get_main_report().add_bounty(self.player, self.target, self.amount)


class Disguise(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player"):
        super().__init__(priority=10, game=game, player=player, fragile=False,
                         public_description=f"{player.name} donned a mask of {target.name}.")
        self.target = target
        self.maintains_hiding = True

    def _act(self):
        get_main_report().apply_face_mask(self.player.name, self.target.name)


class Blackmail(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player"):
        super().__init__(priority=105, game=game, player=player, fragile=False)
        self.target = target
        self.maintains_hiding = True

    def _act(self):
        if not self.target.is_dead() and self.player.check_relative_condition(self.target, Condition.HOOK):
            self.player.report += f"You have blackmailed {self.target.name}." + os.linesep
            self.player.relative_conditions[self.target.name].remove(Condition.HOOK)
            if self.target.has_condition(Condition.HOOK_IGNORE):
                self.target.report += os.linesep + f"Somebody is trying to blackmail you ineffectually." + os.linesep
                self.target.report += "They want you to: INSERT BLACKMAIL" + os.linesep
                self.target.report += "You are free to ignore it." + os.linesep
            else:
                self.target.report += os.linesep + f"You have been blackmailed." + os.linesep
                self.target.report += "You must: INSERT BLACKMAIL" + os.linesep


class Attune(Action):
    def __init__(self, game: Optional['Game'], player: "Player", circuits: Tuple[Element, ...]):
        super().__init__(priority=15, game=game, player=player, fragile=False)
        self.circuits = circuits

    def act(self):
        if self.player.set_attunement(self.circuits):
            self.player.report += f"You attuned to {'/'.join([circuit.name for circuit in self.circuits])}." \
                                  + os.linesep
            if not self.player.has_ability("Quiet Attune"):
                Action.no_class.add(self.player)
                get_main_report().set_attunement(self.player, self.circuits)
            for skill in self.player.get_skills():
                if skill.trigger == Trigger.NONCOMBAT_POST_ATTUNE:
                    HandleSkill(self.game, self.player, skill)

        else:
            self.player.report += f"You tried to attune illegally and failed." + os.linesep


class UseHydro(Action):
    locked: Set['Player'] = set()

    def __init__(self, game: Optional['Game'], player: "Player", ability: "Ability",
                 will: List[int], contingency: bool):
        super().__init__(33 if contingency else -5, game=game, player=player, fragile=False)
        self.ability = ability
        self.will = will
        self.contingency = contingency

    def act(self):
        if self.contingency and self.player not in Action.attacked:
            return

        if self.ability.pin in self.player.hydro_spells:
            return  # Trying to use the same ability twice

        if self.contingency and self.player in UseHydro.locked:
            self.player.report += f"You were prevented from using {self.ability.name}!" + os.linesep
            return

        total_will = sum(self.will)

        if total_will > self.player.willpower:
            self.player.report += f"You cannot use {self.ability.name} because you do not have enough willpower." \
                                  + os.linesep
            return

        if self.ability.pin in QM_ABILITY_PINS:
            print("!"*32)
            print("BE CAREFUL QM".center(32, "!"))
            print("MANUAL INTERVENTION REQUIRED".center(32, "!"))
            print(self.player.name.center(32, "!"))
            print(self.ability.name.center(32, "!"))
            print("!"*32)
            print()
            print()

        self.player.willpower -= total_will
        self.player.report += f"You spent {total_will} willpower casting {self.ability.name}" \
                              f"{' because you were attacked' if self.contingency else ''}." + os.linesep
        self.player.hydro_spells[self.ability.pin] = self.will

        if not self.player.has_ability("Quiet Casting"):
            get_main_report().spend_willpower(self.player, total_will)

        if self.contingency:
            for skill in self.ability.get_skills_for_hydro_contingency(self.will):
                HandleSkill(self.game, self.player, skill)


class Illusion(Action):
    handled: Set['Player'] = set()

    def __init__(self, game: Optional['Game'], player: "Player", target: "Player",
                 fake_action: 'Action', fake_training: Optional['Ability'] = None):
        # Randomly sort multiple illusions on the same target
        super().__init__(12+(random.random()/2.0), game=game, player=player, fragile=False)
        self.target = target
        self.fake_action = fake_action
        self.fake_training = fake_training

    def act(self):
        if not self.player.has_condition(Condition.ILLUSIONIST):
            return

        if self.target not in Illusion.handled:
            self.target.fake_action = self.fake_action
            get_main_report().add_action(self.target, self.fake_action.public_description, fake=True)
            Action.add_action_record(self.target, type(self.fake_action),
                                     target=getattr(self.target.fake_action, 'target', None),
                                     fake=True)
            if isinstance(self.fake_action, Train):
                self.target.fake_ability = self.fake_training
                if self.fake_training:
                    train_name = self.fake_training.name
                    if self.fake_training.pin >= 700:
                        train_name = 'Concept ' + roman.toRoman((self.fake_training.pin % 100))
                    get_main_report().set_training(self.target, train_name)
                else:
                    get_main_report().set_training(self.target, "nothing")

            Illusion.handled.add(self.target)


class MasterIllusion(Action):
    redirect: Dict['Player', Dict['Player', 'Player']] = {}

    def __init__(self, game: Optional['Game'], player: "Player",
                 target: "Player", defended: "Player", redirected: "Player"):
        # Randomly sort multiple illusions on the same target
        super().__init__(12+(random.random()/2.0), game=game, player=player, fragile=False)
        self.target = target
        self.defended = defended
        self.redirected = redirected

    def act(self):
        if not self.player.has_condition(Condition.MASTER_ILLUSIONIST):
            return

        if self.target.is_dead() or self.defended.is_dead() or self.redirected.is_dead():
            return

        self.player.report += f"{self.player.name} befuddled {self.target.name} to confuse {self.defended.name} " \
                              f"with {self.redirected.name}." + os.linesep + os.linesep

        if self.defended not in MasterIllusion.redirect.get(self.target, {}):
            if self.target not in MasterIllusion.redirect:
                MasterIllusion.redirect[self.target] = {}
            MasterIllusion.redirect[self.target][self.defended] = self.redirected
            if isinstance(self.target.action, Attack):
                if self.target.action.target == self.defended:
                    self.target.action.public_description = f"{self.target.name} attacked {self.redirected.name}"
                    self.target.action.combat_on_interrupt = f"while they were attacking {self.redirected.name}"
            elif isinstance(self.target.action, MultiAttack):
                if self.defended in self.target.action.targets:
                    modified_targets = [self.redirected if target == self.defended else target
                                        for target in self.target.action.targets]
                    modified_targets = list(set(modified_targets))
                    target_names = " and ".join([target.name for target in modified_targets])
                    self.target.action.combat_on_interrupt = f"while they were attacking {target_names}"


# Bookkeeping Actions
class NoncombatSkillStep(Action):
    def __init__(self, game: Optional['Game']):
        super().__init__(0, game=game, player=None)

    def act(self):
        for player in Action.players:
            if not player.is_dead():
                if player.concept and not player.has_condition(Condition.AEROMANCER):
                    player.turn_conditions.append(Condition.AEROMANCER)
                if player.has_condition(Condition.HIDING):
                    get_main_report().mark_hiding(player)
                if WORKBENCH in player.items:
                    if isinstance(player.action, Craft):
                        player.turn_conditions.append(Condition.BONUS_BUNKER)
                for skill in player.get_skills():
                    HandleSkill.handle_noncombat_skill(self.game, player, skill)


class TattooStep(Action):
    def __init__(self, game: Optional['Game']):
        super().__init__(9, game=game, player=None)

    def act(self):
        for player in Action.players:
            if not player.is_dead():
                if player.tattoo is not None:
                    rune = get_item(player.tattoo)
                    assert isinstance(rune, Rune)
                    player.report += f"You were empowered by your {rune.get_ability_name()} Tattoo." + os.linesep
                    for skill in rune.get_skills(choice=player.tattoo_choice):
                        skill.targets = player.tattoo_targets
                        if skill.trigger == Trigger.NONCOMBAT:
                            HandleSkill(self.game, player, skill)
                        elif skill.targets and skill.trigger == Trigger.TARGET:
                            HandleSkill(self.game, player, skill, skill.targets)

                    if rune.is_disruptive():
                        if not player.has_ability("Quiet Attune"):
                            Action.no_class.add(player)
                    player.temporary_abilities.append(rune.get_ability_pin())


class ContingencyBlockSimStep(Action):
    def __init__(self, game: Optional['Game']):
        super().__init__(32, game=game, player=None)

    def act(self):
        handler = get_combat_handler()
        UseHydro.locked = handler.drain_sim()


class CombatSimStep(Action):
    def __init__(self, game: Optional['Game']):
        super().__init__(34, game=game, player=None)
        ContingencyBlockSimStep(game)  # Needs to happen before simulation and contingency hydro

    def act(self):
        handler = get_combat_handler()
        fast_attune_players = []
        for player in Action.players:
            if handler.player_in_combat(player):
                if player.has_ability("Fast Attune III"):
                    fast_attune_players.append(player)
                elif handler.player_innocent(player):
                    if player.has_ability("Fast Attune I") or player.has_ability("Fast Attune II"):
                        fast_attune_players.append(player)

        fast_attunes: Dict[Player, Tuple[Element, ...]] = {}
        for reacting_player in fast_attune_players:
            circuit_possibilities = []
            if reacting_player.has_ability("Fast Attune II") or reacting_player.has_ability("Fast Attune III"):
                circuit_possibilities = reacting_player.get_possible_attunement()
            elif reacting_player.has_ability("Fast Attune I"):
                circuit_possibilities = reacting_player.get_one_swap_attunement()
            best_score_so_far = (-999999999999999999, 0, 0)  # Personal score, negative score of others, size attuned
            best_so_far = None
            for possibility in circuit_possibilities:
                sim_results = handler.simulate_combat({reacting_player: possibility})
                secondary = 0
                for sim_player, score in sim_results.items():
                    if sim_player.is_automata and sim_player.owner == reacting_player.name:
                        secondary += score
                    elif reacting_player.name != sim_player.name:
                        secondary -= score
                score = (sim_results[reacting_player], secondary, len(possibility))
                if score > best_score_so_far:
                    best_score_so_far = score
                    best_so_far = possibility
            if best_so_far:
                fast_attunes[reacting_player] = best_so_far

        # We don't set attunement until all simulations have finished to avoid giving an advantage to any player
        for final_player, circuits in fast_attunes.items():
            assert final_player.set_attunement(circuits)
            final_player.report += f"You fast attuned to {'/'.join([circuit.name for circuit in circuits])}." \
                                   + os.linesep
            if not final_player.has_ability("Quiet Attune"):
                get_main_report().set_attunement(final_player, circuits)
                if circuits:
                    Action.no_class.add(final_player)
            final_player.tentative_conditions.clear()
            for skill in final_player.get_skills():
                if skill.trigger == Trigger.NONCOMBAT_POST_ATTUNE:
                    HandleSkill(self.game, final_player, skill)


class CombatStep(Action):
    def __init__(self, game: Optional['Game']):
        super().__init__(35, game=game, player=None)

    def act(self):
        was_alive = {player: not player.is_dead() for player in Action.players}

        get_combat_handler().process_all_combat()

        for player in Action.players:
            player.report += COMBAT_PLACEHOLDER + os.linesep + os.linesep

            if get_combat_handler().hot_blood_check(player) and player.temperament == Temperament.HOT_BLOODED:
                if not player.is_dead() or player.has_condition(Condition.RESURRECT):
                    player.report += "Your blood boils in excitement." + os.linesep
                    Action.progress(player, 3)
                    player.report += os.linesep

            if not player.is_dead():
                for skill in player.get_skills():
                    if skill.trigger == Trigger.POST_COMBAT:
                        HandleSkill(self.game, player, skill)
                if player.tattoo is not None:
                    rune = get_item(player.tattoo)
                    assert isinstance(rune, Rune)
                    for skill in rune.get_skills():
                        if skill.trigger == Trigger.POST_COMBAT:
                            HandleSkill(self.game, player, skill)
                for item in player.get_consumed_items():
                    for skill in item.get_skills():
                        if skill.trigger == Trigger.POST_COMBAT:
                            HandleSkill(self.game, player, skill)
            elif was_alive[player]:
                player.report += os.linesep
                player.destroy_fragile_items(include_loot=True)
                player.report += os.linesep
        for player in get_combat_handler().full_escape:
            get_main_report().add_action(player, f"{player.name} escaped combat.")
            self.interrupted_players.discard(player)


class ProgressStep(Action):
    def __init__(self, game: Optional['Game'], skip_intuitive: bool = False):
        super().__init__(90, game=game, player=None)
        self.skip_intuitive = skip_intuitive

    def act(self):
        if not self.skip_intuitive:
            for player in self.game.players.values():
                if player.is_dead():
                    continue

                if player.temperament == Temperament.INTUITIVE:
                    if player not in Action.interrupted_players or not player.action.fragile:
                        player.report += "Intuitive: "
                        Action.progress(player, 1)
                        player.report += os.linesep

        was_progress = False
        for player in Action.progress_dict:
            if player.is_dead():
                continue

            if Action.progress_dict.get(player) > 0:
                player.gain_progress(Action.progress_dict[player])
                Action.progress_dict[player] = 0
                was_progress = True

        if was_progress:
            # It is possible for abilities to give progress
            ProgressStep(self.game, skip_intuitive=True)


class WillpowerStep(Action):
    def __init__(self, game: Optional['Game'],):
        super().__init__(130, game=game, player=None)

    def act(self):
        if self.game:
            for player in Action.players:
                if not player.is_dead():
                    player.max_willpower = 0
                    for skill in player.get_skills(include_this_turn=True):
                        if skill.effect == Effect.MAX_WILLPOWER:
                            player.max_willpower += skill.value
                    if player.max_willpower:
                        player.report += os.linesep
                        if self.game.is_night() or player.has_ability("Rapid Regen II", ignore_this_turn=False):
                            if player.has_ability("Rapid Regen I", ignore_this_turn=False):
                                regen = player.max_willpower
                            else:
                                regen = player.max_willpower // 2 + (player.max_willpower % 2)  # Divide by 2 round up
                            regen = min(regen, player.max_willpower-player.willpower)
                            if regen:
                                player.report += f"You regained {regen} willpower." + os.linesep
                                player.willpower += regen
                        player.report += f"{player.willpower}/{player.max_willpower} Willpower" + os.linesep


class StatusChangeStep(Action):
    def __init__(self, game: Optional['Game'],):
        super().__init__(140, game=game, player=None)

    def act(self):
        for player in Action.players:
            if not player.is_dead():
                player.report += os.linesep
                if Condition.PETRIFIED in player.conditions:
                    if player not in Action.not_wandering:
                        get_main_report().add_action(player, f"{player.name} was stuck as a Statue.")
                    player.conditions.remove(Condition.PETRIFIED)
                    count = player.conditions.count(Condition.PETRIFIED)
                    if count:
                        turn = "turn"
                        if count > 1:
                            turn += "s"
                        player.report += f"You are Petrified. You will be free after {count} {turn}." + os.linesep
                    else:
                        player.report += f"You have broken free from your Petrification." + os.linesep
                        get_main_report().broadcast(f"{player.name} has escaped Petrification.")
                elif Condition.GRIEVOUS in player.conditions:
                    # Just using the count of Grievous to mark lethality
                    player.conditions.append(Condition.GRIEVOUS)
                    count = player.conditions.count(Condition.GRIEVOUS)
                    if count >= 4:
                        player.die(f"{player.name} succumbed to their wounds and died.")
                    else:
                        turn = "turn"
                        if count != 3:
                            turn += 's'
                        player.report += f"You are grievously wounded you must heal " \
                                         f"within {4-count} {turn} or you will die." + os.linesep

                if self.game.is_night():
                    if not player.is_automata:
                        if player.temperament == Temperament.LUCRATIVE:
                            player.gain_credits(2)
                            player.report += f"Student Services has granted you 2 credits " \
                                             f"({player.get_credits()} total)." \
                                             + os.linesep + os.linesep
                        else:
                            player.gain_credits(1)
                            player.report += f"Student Services has granted you 1 credit " \
                                             f"({player.get_credits()} total)." \
                                             + os.linesep + os.linesep


class Resurrect(Action):
    def __init__(self, game: Optional['Game'], player: "Player", stealth: bool = False):
        super().__init__(priority=36, game=game, player=player, fragile=False,
                         public_description=f"{player.name} rose from the dead." if not stealth else "")
        self.stealth = stealth

    def act(self):
        if not self.player.is_dead():
            return
        if not self.stealth:
            get_main_report().add_action(self.player, f"{self.player.name} died.")
        super().act()

    def _act(self):
        # Delete stealable items and fragile items
        self.player.conditions = [condition for condition in self.player.conditions if condition not in AFFLICTIONS]
        self.player.conditions.append(Condition.INJURED)
        if self.stealth:
            self.player.report += "You came back from the dead." + os.linesep
        self.player.report += "You came back with an injury." + os.linesep
        if self.stealth:
            self.player.conditions.append(Condition.HIDING)
            self.player.turn_conditions.append(Condition.FRESH_HIDING)
            get_main_report().mark_hiding(self.player)


def reset_action_handler():
    Action.tic_index = 0
    Action.queue = PriorityQueue()
    Action.players = set()
    Action.not_wandering = set()
    Action.interrupted_players = set()
    Action.attacked = set()
    Action.progress_dict = {}
    Action.no_class = set()  # Used poison gas or attuned
    # Used for conditional trades based on actions
    Action.action_record = []
    Action.spied = {}
    Action.fake_action_record = []
    Action.fake_spied = {}

    # Used for teaching/learning handshake
    # Teacher: Student
    Action.teacher_student = {}
    # Student: Teacher
    Action.student_teacher = {}
    # Teacher: Ability
    Action.teacher_ability = {}
    # Used to allow Altruism to work when multiple players heal the same injured player
    Action.was_healed = set()

    # Used for tattoo coordination
    # Artist: Canvas
    Action.artist_canvas = {}
    # Canvas: Artist
    Action.canvas_artist = {}
    # Artist: Rune
    Action.artist_rune = {}

    HandleSkill.info_once_dict = {}
    HandleSkill.info_once_broadcast = set()

    Steal.victim_to_thieves = {}
    StealFollow.handled = set()

    ConsumeItem.unique_pair = set()

    Trade.unique_pair = set()
    # {(Sender, Recipient): (Credits, {Item: Amount})}
    Trade.item_conditions = {}
    # Used to prevent a player from promising the same items/credits to multiple players
    Trade.reserved = {}

    Illusion.handled.clear()
    MasterIllusion.redirect.clear()

    UseHydro.locked.clear()
