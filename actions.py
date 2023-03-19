import os
from queue import PriorityQueue
from typing import TYPE_CHECKING, Set, Dict, Optional, Tuple, List, Type

from ability import Ability, get_ability
from combat import get_combat_handler
from constants import Temperament, Condition, Trigger, Effect, InfoScope, \
    COMBAT_PLACEHOLDER, SELF_PLACEHOLDER, TARGET_PLACEHOLDER, InjuryModifier, Element
from items import get_item_by_name, get_item, Item, Rune
from report import DayReport

if TYPE_CHECKING:
    from game import Game
    from player import Player
    from skill import Skill

POISON_GAS = get_item_by_name("Poison Gas").pin
SHROOMS = get_item_by_name("Shrooms").pin
MEDKIT = get_item_by_name("Medkit").pin
DEPLETED_MEDKIT = get_item_by_name("1/2 Medkit").pin
LIQUID_MEMORIES = get_item_by_name("Liquid Memories").pin
HEALING_TANK = get_item_by_name("Healing Tank").pin
BOOBY_TRAP = get_item_by_name("Booby Trap").pin

# For conditional trading
# Player action target
ACTION_CONDITION = Tuple['Player', Type['Action'], Optional['Player']]
# Player, minimum credits, minimum items
ITEM_CONDITION = Tuple['Player', int, Dict['Item', int]]


def noncombat_wound(source: 'Player', victim: 'Player', modifiers: List[InjuryModifier] = None):
    if not modifiers:
        modifiers = []

    if source.has_condition(Condition.INFLICT_CAUTERIZE):
        modifiers.append(InjuryModifier.PERMANENT)
    if source.has_condition(Condition.INFLICT_GRIEVOUS):
        modifiers.append(InjuryModifier.GRIEVOUS)

    if victim.has_condition(Condition.GRIEVOUS_IMMUNE):
        if InjuryModifier.GRIEVOUS in modifiers and InjuryModifier.PERMANENT not in modifiers:
            modifiers = [modifier for modifier in modifiers if modifier != InjuryModifier.GRIEVOUS]

    victim.wound(injury_modifiers=modifiers)


class Action:
    tic_index = 0

    queue = PriorityQueue()
    players: Set['Player'] = set()
    not_wandering: Set['Player'] = set()
    interrupted_players: Set['Player'] = set()
    progress_dict: Dict['Player', int] = {}
    no_class: Set['Player'] = set()  # Used poison gas or attuned

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
        Action.tic_index += 1

        if self.game and not game.simulation:  # Hack to make fake actions
            Action.queue.put(self)

    def act(self):
        interrupted = self.player in Action.interrupted_players

        if not interrupted or not self.fragile:
            if self.public_description:
                DayReport().add_action(self.player, self.public_description)
                self.player.report += self.public_description + os.linesep
        if interrupted and self.fragile:
            DayReport().add_action(self.player, self.on_interrupt)
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
        # WillpowerStep(game)
        StatusChangeStep(game)

        while not cls.queue.empty():
            tic = cls.queue.get()
            if not tic.player or Action.can_act(tic.player):
                tic.act()
            elif Condition.PETRIFIED in tic.player.conditions:
                DayReport().add_petrification(tic.player)

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
            Action.fake_action_record.append((player, action, target))
        else:
            Action.action_record.append((player, action, target))
        # TODO handle illusions

    @classmethod
    def check_action_record(cls, game: 'Game', observer: 'Player', condition: ACTION_CONDITION) -> bool:
        if not game.is_day() and not observer.has_ability("Panopticon"):
            if condition[0] != observer:
                if condition[0] not in Action.spied.get(observer, []):
                    if not condition[2] == observer or condition[1] not in [Teach, Learn, Heal]:
                        # Can't validate action for condition
                        return False

            if condition[0] in Action.fake_spied.get(observer, []):
                for record in Action.fake_action_record:
                    if record[0] == condition[0]:
                        if record[1] == condition[1]:
                            if not condition[2] or record[2] == condition[2]:
                                return True
                return False

        for record in Action.action_record:
            if record[0] == condition[0]:
                if record[1] == condition[1]:
                    if not condition[2] or record[2] == condition[2]:
                        return True
        return False


class HandleSkill(Action):
    def __init__(self, game: Optional['Game'], player: "Player", skill: 'Skill',
                 target: Optional['Player'] = None, fake: bool = False):
        super().__init__(priority=skill.priority, game=game, player=player, fragile=False)
        self.target = target
        self.skill = skill
        self.fake = fake  # Used to disguise that copycat and trade secrets fail vs counter int

    def act(self):
        if self.skill.self_has_condition and not self.player.has_condition(self.skill.self_has_condition):
            return
        if self.skill.self_not_condition and self.player.has_condition(self.skill.self_not_condition):
            return

        if self.target:
            if self.skill.target_has_condition and not self.target.has_condition(self.skill.target_has_condition):
                return
            if self.skill.target_not_condition and self.target.has_condition(self.skill.target_not_condition):
                return

        if self.skill.text:
            text = self.skill.text.replace(SELF_PLACEHOLDER, self.player.name)
            if self.target:
                text = text.replace(TARGET_PLACEHOLDER, self.target.name)

            if self.skill.info == InfoScope.PRIVATE:
                self.player.report += text + os.linesep
            elif self.skill.info == InfoScope.PUBLIC:
                DayReport().add_action(self.player, text)
            elif self.skill.info == InfoScope.BROADCAST:
                DayReport().broadcast(text)

        if self.skill.effect == Effect.CONDITION:
            if not self.fake:
                self.player.turn_conditions.append(Condition[self.skill.value])
        elif self.skill.effect == Effect.TENTATIVE_CONDITION:
            if not self.fake:
                self.player.tentative_conditions.append(Condition[self.skill.value])
        elif self.skill.effect == Effect.REL_CONDITION:
            if not self.target:
                raise Exception("No target for relative condition?")
            if not self.fake:
                self.player.add_relative_condition(self.target, Condition[self.skill.value])
        elif self.skill.effect == Effect.DEV_SABOTAGE:
            if not self.target:
                raise Exception("No target for dev sabotage?")
            if not self.fake:
                self.target.dev_sabotaged(self.skill.text.replace(SELF_PLACEHOLDER, "somebody")
                                          .replace(TARGET_PLACEHOLDER, self.target.name))
        elif self.skill.effect == Effect.COPYCAT:
            if not self.target:
                raise Exception("No target for copycat?")
            self.player.copycat(self.target, fake=self.fake)
        elif self.skill.effect == Effect.PROGRESS:
            if not self.fake:
                Action.progress(self.player, self.skill.value)

        else:
            raise Exception(f"Unhandled effect type in noncombat! {self.skill.effect.name}")


class Wander(Action):
    def __init__(self, game: Optional['Game'], player: "Player"):
        super().__init__(priority=80, game=game, player=player, fragile=True,
                         public_description=f"{player.name} wandered aimlessly.",
                         on_interrupt=f"{player.name} failed to wander aimlessly.")

    def act(self):
        if self.player not in Action.not_wandering:
            super().act()


# Universal Actions

# Adds player to combat
class Attack(Action):
    def __init__(self, game: "Game", player: "Player", target: "Player"):
        super().__init__(priority=30, game=game, player=player, fragile=False,
                         public_description=f"{player.name} attacked {target.name}",
                         combat_on_interrupt=f"while they were attacking {target.name}")
        self.target = target

    def act(self):
        if self.target.is_dead():
            # Player will wander aimlessly
            pass
        else:
            if self.target.action.combat_on_interrupt:
                self.public_description += " " + self.target.action.combat_on_interrupt
            self.public_description += "."
            Action.interrupted_players.add(self.target)
            get_combat_handler().add_attack(self.player, self.target)

            # The combat handler will ensure it gets added to the players regular report
            DayReport().add_action(self.player, self.public_description)
            Action.not_wandering.add(self.player)
            Action.add_action_record(self.player, Attack, self.target)


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
            DayReport().add_action(self.player, f"{self.player.name} learned from {self.target.name}.")
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
            DayReport().add_action(self.player, f"{self.player.name} taught {self.target.name}.")
            self.player.report += f"{self.player.name} taught {self.target.name} {self.ability.name}." + os.linesep
            if self.player.temperament == Temperament.ALTRUISTIC:
                Action.progress(self.player, 8)
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
        if self.player.temperament == Temperament.INTUITIVE:
            Action.progress(self.player, 1)
        Action.add_action_record(self.player, Train)
        if not self.player.dev_plan:
            DayReport().set_training(self.player, "nothing")
        else:
            DayReport().set_training(self.player, get_ability(self.player.dev_plan[0]).name)


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
        self.player.academics += 1
        self.player.report += f"Academics ({self.player.academics})"+os.linesep
        if self.player.temperament == Temperament.SCHOLASTIC:
            Action.progress(self.player, 3)
        Action.add_action_record(self.player, Class)


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


class Shop(Action):
    def __init__(self, game: Optional['Game'], player: "Player", items: Dict['Item', int]):
        super().__init__(priority=40, game=game, player=player, fragile=True,
                         public_description=f"{player.name} shopped.",
                         combat_on_interrupt="while they were trying to shop")
        self.items = items

    def act(self):
        if Shop.get_total_cost(self.items) > self.player.credits:
            self.player.report += f"{self.player.name} was kicked out of shop club for not having enough credits." \
                                  + os.linesep
        else:
            super().act()

    def _act(self):
        total_cost = Shop.get_total_cost(self.items)
        self.player.lose_credits(total_cost)
        self.player.report += f"{self.player.name} spent {total_cost} credits ({self.player.credits} remaining)." \
                              + os.linesep
        for item, amount in self.items.items():
            self.player.gain_item(item, amount)
        Action.add_action_record(self.player, Shop)
        DayReport().add_shop(self.player, total_cost, self.items)

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
                was_injured = Condition.INJURED in self.target.conditions
                if was_injured:
                    Action.was_healed.add(self.target)
                if self.target.heal():
                    self.player.report += f"{self.player.name} treated {self.target.name}, " \
                                          f"but they remain wounded." + os.linesep
                    self.target.report += f"{self.player.name} treated {self.target.name}, " \
                                          f"but {self.target.name} remain wounded." + os.linesep
                else:
                    self.player.report += f"{self.player.name} treated {self.target.name} and they are now healthy." \
                                          + os.linesep
                    self.target.report += f"{self.player.name} treated {self.target.name} " \
                                          f"and {self.target.name} is now healthy." + os.linesep
                if self.player.temperament == Temperament.ALTRUISTIC:
                    if was_injured or self.target in Action.was_healed:
                        Action.progress(self.player, 8)
                    else:
                        self.player.report += f"{self.target.name} did not require treatment." + os.linesep
                Action.add_action_record(self.player, Heal, self.target)


class Steal(Action):
    victim_to_thieves: Dict['Player', Set['Player']] = {}

    def __init__(self, game: Optional['Game'], player: "Player", target: "Player"):
        super().__init__(priority=60, game=game, player=player, fragile=True,
                         public_description=f"{player.name} robbed {target.name}.",
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
            involved = " and ".join(sorted([DayReport().face_mask_replacement(player.name, self.player.name)
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
            noncombat_wound(self.target, self.player, [InjuryModifier.NONLETHAL])
            DayReport().broadcast(f"A booby trap exploded in {self.player.name}'s face!")

        if self.target not in StealFollow.handled:
            StealFollow.handled.add(self.target)
            self.target.report += "Somebody robbed you!" + os.linesep
            for item, amount in self.items.items():
                self.target.lose_item(item, amount)
            self.target.destroy_fragile_items()


class Craft(Action):
    def __init__(self, game: Optional['Game'], player: "Player", items: Dict['Item', int], is_bonus: bool = False):
        super().__init__(priority=40, game=game, player=player, fragile=True,
                         public_description=f"{player.name} crafted.",
                         combat_on_interrupt=f"while they were trying to craft something")
        self.items = items
        self.is_bonus = is_bonus

    def act(self):
        if not self.items:
            return

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
                    self.player.report += f"You don't know have the ability to make a rune " \
                                          f"for {item.get_ability_name()}." + os.linesep
                    return
            # Todo hydro crafting/willpower check

        if rune_crafting and len(self.items) > 1:
            # Can only craft 1 rune at a time, if crafting ANY runes.
            return

        if self.is_bonus and rune_crafting:
            if not self.player.has_ability("Rune Crafting II"):
                return  # Player cannot bonus rune craft

        super().act()

    def _act(self):
        for item, amount in self.items.items():
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
            DayReport().add_action(self.player, f"{self.player.name} got tattooed by {self.target.name}.")
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

    def act(self):
        if self.self_target:
            if self.player.tattoo:
                self.player.report += "You already have a tattoo." + os.linesep
                return
        if not self.player.has_ability("Runic Tattoos"):
            return
        super().act()

    def _act(self):
        able_to_tattoo = self.player.has_ability("Runic Tattoos")
        if not self.player.has_ability("Rune Crafting I") and not self.player.has_ability("Rune Crafting II"):
            able_to_tattoo = False
        if not self.rune.is_simple_rune() and not self.player.has_ability("Rune Crafting II"):
            able_to_tattoo = False
        if not self.player.has_ability(self.rune.get_ability_name(), strict=True):
            able_to_tattoo = False

        if not able_to_tattoo:
            self.player.report += f"You were incapable of making the {self.rune.name} Tattoo." + os.linesep

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
            DayReport().add_action(self.player, f"{self.player.name} tattooed {self.target.name}.")
            self.player.report += f"{self.player.name} tattooed {self.target.name} " \
                                  f"with {self.rune.name}." + os.linesep
            if self.player.temperament == Temperament.ALTRUISTIC:
                Action.progress(self.player, 8)
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

        interruption_strings = []
        attacked_someone = False
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

                Action.add_action_record(self.player, Attack, target)
        if attacked_someone:
            self.public_description += (" and ".join(interruption_strings))[:-1]
            self.public_description += "."

            DayReport().add_action(self.player, self.public_description)
            Action.not_wandering.add(self.player)


# Bonus Actions

class Spy(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player"):
        super().__init__(priority=85, game=game, player=player, fragile=False,
                         public_description=f"{player.name} spied on {target.name}.")
        self.target = target

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
        self.player.report += DayReport().get_spy_report(self.player, self.target, counter_int) + os.linesep
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
                HandleSkill(self.game, self.player, skill, self.target, fake=counter_int)

        for skill in self.target.get_skills():
            if skill.trigger == Trigger.SPIED_ON:
                HandleSkill(self.game, self.target, skill, self.player)


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
            for skill in self.item.get_skills():
                if skill.trigger == Trigger.NONCOMBAT:
                    HandleSkill(self.game, self.player, skill)
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
    reserved: Dict['Player', Tuple[int, Dict['Item', int]]] = {}

    def __init__(self, game: Optional['Game'], player: "Player", target: "Player",
                 items: Optional[Dict['Item', int]] = None, money: int = 0,
                 action_condition: Optional[ACTION_CONDITION] = None,
                 item_condition: Optional[ITEM_CONDITION] = None):
        if (player, target) in Trade.unique_pair:
            raise Exception(f"{player.name} is trying to trade with {target.name} multiple times")
        if money < 0:
            raise Exception(f"{player.name} is trying to give away negative money.")
        if not money and not items:
            raise Exception(f"{player.name} is trying to place an empty trade.")
        if items is None:
            items = {}
        super().__init__(100, game=game, player=player, fragile=False)
        self.target = target
        self.items = items
        self.credits = money
        self.action_condition = action_condition
        self.item_condition = item_condition
        Trade.unique_pair.add((player, target))

    def act(self):
        if self.action_condition:
            if not Action.check_action_record(self.game, self.player, self.action_condition):
                self.player.report += f"You did not trade with {self.target.name} " \
                                      f"because the required action did not happen." + os.linesep
                return
        failed_trade = False
        reserved_credits, reserved_items = Trade.reserved.get(self.player, (0, {}))
        if self.credits:
            reserved_credits += self.credits
            if self.player.credits < reserved_credits:
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
        Trade.reserved[self.player] = (reserved_credits, reserved_items)
        if failed_trade:
            return
        Trade.item_conditions[(self.player, self.target)] = (self.credits, self.items)
        TradeFollow(self.game, self.player, self.target, self.items, self.credits, self.item_condition)


# Used only by Trade
class TradeFollow(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player",
                 items: Optional[Dict['Item', int]], money: int,
                 item_condition: Optional[ITEM_CONDITION]):
        super().__init__(101, game=game, player=player, fragile=False)
        self.target = target
        self.items = items
        self.credits = money
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
        TradeFinal(self.game, self.player, self.target, self.items, self.credits, self.item_condition)


# Used only by Trade
class TradeFinal(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player",
                 items: Optional[Dict['Item', int]], money: int,
                 item_condition: Optional[ITEM_CONDITION]):
        super().__init__(102, game=game, player=player, fragile=False)
        self.target = target
        self.items = items
        self.credits = money
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
                                  f"({self.player.credits} remaining)." \
                                  + os.linesep
            self.target.gain_credits(self.credits)
            self.target.report += f"{self.player.name} sent you {self.credits} credits " \
                                  f"({self.target.credits} total)." \
                                  + os.linesep
        if self.items:
            self.player.report += f"You sent {self.target.name} items." + os.linesep
            self.target.report += f"{self.player.name} sent you items." + os.linesep
            for item, amount in self.items.items():
                self.player.lose_item(item, amount)
                self.target.gain_item(item, amount)
        DayReport().add_trade(self.player, self.target, self.credits, self.items)


class Disguise(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player"):
        super().__init__(priority=10, game=game, player=player, fragile=False,
                         public_description=f"{player.name} donned a mask of {target.name}.")
        self.target = target

    def _act(self):
        DayReport().apply_face_mask(self.player.name, self.target.name)


class Blackmail(Action):
    def __init__(self, game: Optional['Game'], player: "Player", target: "Player"):
        super().__init__(priority=105, game=game, player=player, fragile=False)
        self.target = target

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
    def __init__(self, game: Optional['Game'], player: "Player", circuits: Tuple[Element]):
        super().__init__(priority=15, game=game, player=player, fragile=False)
        self.circuits = circuits

    def act(self):
        if self.player.set_attunement(self.circuits):
            self.player.report += f"You attuned to {'/'.join([circuit.name for circuit in self.circuits])}." \
                                  + os.linesep
            if not self.player.has_ability("Quiet Attune"):
                Action.no_class.add(self.player)
                DayReport().set_attunement(self.player, self.circuits)
            for skill in self.player.get_skills():
                if skill.trigger == Trigger.NONCOMBAT_POST_ATTUNE:
                    HandleSkill(self.game, self.player, skill)

        else:
            self.player.report += f"You tried to attune illegally and failed." + os.linesep


# Bookkeeping Actions
class NoncombatSkillStep(Action):
    def __init__(self, game: Optional['Game']):
        super().__init__(0, game=game, player=None)

    def act(self):
        for player in Action.players:
            if not player.is_dead():
                for skill in player.get_skills():
                    if skill.trigger == Trigger.NONCOMBAT:
                        HandleSkill(self.game, player, skill)


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
                    for skill in rune.get_skills():
                        if skill.trigger == Trigger.NONCOMBAT:
                            HandleSkill(self.game, player, skill)

                    if rune.is_disruptive():
                        if not player.has_ability("Quiet Attune"):
                            Action.no_class.add(player)
                    player.temporary_abilities.append(rune.get_ability_pin())


class CombatSimStep(Action):
    def __init__(self, game: Optional['Game']):
        super().__init__(34, game=game, player=None)

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

        fast_attunes: Dict[Player, Tuple[Element]] = {}
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
                    if reacting_player.name != sim_player.name:
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
                DayReport().set_attunement(final_player, circuits)
            final_player.tentative_conditions.clear()
            for skill in final_player.get_skills():
                if skill.trigger == Trigger.NONCOMBAT_POST_ATTUNE:
                    HandleSkill(self.game, final_player, skill)


class CombatStep(Action):
    def __init__(self, game: Optional['Game']):
        super().__init__(35, game=game, player=None)

    def act(self):
        get_combat_handler().process_all_combat()

        for player in Action.players:
            player.report += COMBAT_PLACEHOLDER + os.linesep + os.linesep

            if get_combat_handler().hot_blood_check(player) and player.temperament == Temperament.HOT_BLOODED:
                Action.progress(player, 3)

            if not player.is_dead():
                for skill in player.get_skills():
                    if skill.trigger == Trigger.POST_COMBAT:
                        HandleSkill(self.game, player, skill)


class ProgressStep(Action):
    def __init__(self, game: Optional['Game']):
        super().__init__(90, game=game, player=None)

    def act(self):
        for player, progress in Action.progress_dict.items():
            if player.is_dead():
                continue

            if progress > 0:
                player.gain_progress(progress)


class StatusChangeStep(Action):
    def __init__(self, game: Optional['Game'],):
        super().__init__(140, game=game, player=None)

    def act(self):
        for player in Action.players:
            if not player.is_dead():
                if Condition.PETRIFIED in player.conditions:
                    player.conditions.remove(Condition.PETRIFIED)
                    count = player.conditions.count(Condition.PETRIFIED)
                    if count:
                        turn = "turn"
                        if count > 1:
                            turn += "s"
                        player.report += f"You are Petrified. You will be free after {count} {turn}." + os.linesep
                    else:
                        player.report += f"You have broken free from your Petrification." + os.linesep
                        DayReport().broadcast(f"{player.name} has escaped Petrification.")
                elif Condition.GRIEVOUS in player.conditions:
                    # Just using the count of Grievous to mark lethality
                    player.conditions.append(Condition.GRIEVOUS)
                    count = player.conditions.count(Condition.GRIEVOUS)
                    if count >= 4:
                        player.report += "You have succumbed to your wounds and died." + os.linesep
                        DayReport().broadcast(f"{player.name} succumbed to their wounds and died.")
                        player.conditions.append(Condition.DEAD)
                    else:
                        turn = "turn"
                        if count != 3:
                            turn += 's'
                        player.report += f"You are grievously wounded you must heal " \
                                         f"within {4-count} {turn} or you will die." + os.linesep


def reset_action_handler():
    Action.tic_index = 0
    Action.queue = PriorityQueue()
    Action.players = set()
    Action.not_wandering = set()
    Action.interrupted_players = set()
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

    Steal.victim_to_thieves = {}
    StealFollow.handled = set()

    ConsumeItem.unique_pair = set()

    Trade.unique_pair = set()
    # {(Sender, Recipient): (Credits, {Item: Amount})}
    Trade.item_conditions = {}
    # Used to prevent a player from promising the same items/credits to multiple players
    Trade.reserved = {}
