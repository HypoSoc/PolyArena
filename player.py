import itertools
import os
from typing import Dict, List, NoReturn, Optional, Set, Tuple, Type, Union, Iterable, TYPE_CHECKING

from ability import get_ability, Ability, get_ability_by_name
from actions import Action, Wander, Class, Train, Bunker, Attack, ConsumeItem, Doctor, Teach, Learn, Heal, Shop, \
    ITEM_CONDITION, Trade, ACTION_CONDITION, Disguise, Spy, Blackmail, Taunt, Steal, Attune, Craft, Tattoo, Canvas, \
    MultiAttack, UseHydro, Resurrect, Illusion, MasterIllusion, PlaceBounty, HandleSkill, SendMessage
from combat import get_combat_handler
from constants import Temperament, Condition, ItemType, InjuryModifier, InfoScope, COMBAT_PLACEHOLDER, Element, Trigger
from game import Game
from items import Item, get_item, get_item_by_name, Rune
from report import ReportCallable, get_main_report
from skill import Skill

if TYPE_CHECKING:
    from automata import Automata

FACE_MASK = get_item_by_name("Face Mask").pin
LIZARD_TAIL = get_item_by_name("Lizard Tail").pin
MEDKIT = get_item_by_name("Medkit").pin
DEPLETED_MEDKIT = get_item_by_name("1/2 Medkit").pin
SOFT = get_item_by_name("Soft").pin
AUTOMATA = get_item_by_name("Automata").pin
DIMENSIONAL_KEY = get_item_by_name("Dimensional Key").pin

CONCEPT_I = get_ability_by_name("Dummy Concept I").pin
LEGACY_MAGIC = get_ability_by_name("Legacy Magic").pin
REALITY_IMPOSITION = get_ability_by_name("Reality Imposition").pin

CONSUME_PREFER = {MEDKIT: DEPLETED_MEDKIT}


class Player:
    def __init__(self, name: str, progress_dict: Dict[int, int], dev_plan: List[int], academics: int,
                 temperament: Temperament, concept: Optional[str],
                 conditions: List[Condition], items: List[int], money: int,
                 willpower: int, bounty: int,
                 relative_conditions: Dict[str, List[Condition]], tattoo: Optional[int],
                 crafted_before: List[int],
                 game: Game):
        assert "%" not in name, "Illegal character %"

        self.name = name
        self.progress_dict = progress_dict
        self.academics = academics
        self.temperament = temperament
        self.concept = concept.upper() if concept else None
        self.items = items
        self.conditions = conditions
        self.credits = money
        self.willpower = willpower
        self.bounty = bounty
        # Used for Hooks, Know thy enemy, and aeromancy_abilities
        self.relative_conditions = relative_conditions
        self.tattoo = tattoo  # Rune item pin
        self.crafted_before = crafted_before
        self.game = game

        self.consuming = False
        self.masking = False
        self.attuning = False

        self.message_count = 0

        aeromancer = set()

        complete_ability_pins = [None]
        for (ability_pin, progress) in progress_dict.items():
            ability = get_ability(ability_pin)
            if progress < 0 or progress > ability.cost:
                raise Exception(f"Player {name} has an illegal progress value "
                                f"{progress} for {ability.name} ({ability_pin})")
            if progress == ability.cost:
                complete_ability_pins.append(ability_pin)
                if ability.concept:
                    aeromancer.add(ability.concept.upper())
                if self.game.turn <= 0:
                    for skill in ability.get_skills([], [], choice=0):
                        if skill.trigger in [Trigger.ACQUISITION, Trigger.START_OF_GAME]:
                            HandleSkill(self.game, self, skill)

        for (ability_pin, progress) in progress_dict.items():
            ability = get_ability(ability_pin)
            if progress > 0:
                if ability_pin == LEGACY_MAGIC:
                    legacy_prereqs = [
                        pin for pin in complete_ability_pins if pin in range(601, 10001, 100)]
                    if not len(legacy_prereqs):
                        raise Exception(f"Player {name} is missing prerequisite "
                                        f"for ability {ability.name}")
                elif ability_pin == REALITY_IMPOSITION:
                    legacy_prereqs = [
                        pin for pin in complete_ability_pins if pin in range(603, 10003, 100)]
                    if not len(legacy_prereqs):
                        raise Exception(f"Player {name} is missing prerequisite "
                                        f"for ability {ability.name}")
                elif ability.prerequisite_pin not in complete_ability_pins:
                    raise Exception(f"Player {name} is missing prerequisite "
                                    f"for ability {ability.name} ({ability.get_prerequisite().name})")

        assert len(aeromancer) <= 1 or 'X' in aeromancer
        if not self.concept and len(aeromancer):
            if 'X' in aeromancer:
                assert len(aeromancer) == 3
                aeromancer.remove('X')
                aeromancer_list = sorted(list(aeromancer))
                self.concept = f"{aeromancer_list[0]} X {aeromancer_list[1]}"
            else:
                self.concept = list(aeromancer)[0]

        self.dev_plan = dev_plan
        self._validate_dev_plan(
            self.dev_plan, complete_ability_pins, self.name)

        self.report = ""
        self.action = Wander(self.game, self)
        self.bonus_action = None
        self.distracted = False

        self.fake_action = Wander(None, self)
        self.fake_ability: Optional['Ability'] = None

        self.disabled_ability_pins: Set[int] = set()
        self.consumed_items: Set[int] = set()
        self.turn_conditions = []
        self.circuits: Iterable[Element] = []
        self.tentative_conditions = []
        # Used for non skill based abilities from runes
        self.temporary_abilities: List[int] = []
        # Used for skills granted toa  player for a turn
        self.temporary_skills: List[Skill] = []

        self.max_willpower = 0  # Comes from abilities
        self.hydro_spells: Dict[int, List[int]] = {}

        self.ability_targets: Dict[int, List[Player]] = {}
        self.ability_choices: Dict[int, int] = {}
        self.item_targets: Dict[int, List[Player]] = {}
        self.item_choices: Dict[int, int] = {}
        self.tattoo_targets: List[Player] = []
        self.tattoo_choice: int = -1

        self.used_illusion = False
        # bookkeeping to prevent multiple bounty placements
        self.bounties_placed: Set['Player'] = set()
        # bookkeeping to prevent multiple blackmail placements
        self.blackmail_placed: Set['Player'] = set()
        # bookkeeping to prevent multiple taunt placements
        self.taunt_placed: Set['Player'] = set()

        self.is_automata = False
        self.owner = None
        # Used so that automata can be traded the same turn they are created
        self.automata_registry: Dict[str, 'Automata'] = {}

        self.abilities_gained_this_turn: List[int] = []

        game.register(self)

    def make_copy_for_simulation(self, game: 'Game') -> 'Player':
        clone = Player(name=self.name + "_CLONE", progress_dict=self.progress_dict.copy(),
                       dev_plan=self.dev_plan.copy(),
                       academics=self.academics, temperament=self.temperament, concept=self.concept,
                       conditions=self.conditions.copy(),
                       items=self.items.copy(), money=self.credits, willpower=self.willpower, bounty=self.bounty,
                       relative_conditions={
                           k: v[:] for k, v in self.relative_conditions.items()},
                       tattoo=self.tattoo, crafted_before=self.crafted_before,
                       game=game)
        clone.disabled_ability_pins = set()
        clone.consumed_items = self.consumed_items.copy()
        clone.turn_conditions = self.turn_conditions.copy()
        clone.tentative_conditions = self.tentative_conditions.copy()
        clone.temporary_abilities = self.temporary_abilities.copy()
        clone.temporary_skills = self.temporary_skills.copy()
        clone.ability_choices = self.ability_choices.copy()
        clone.item_choices = self.item_choices.copy()
        clone.circuits = self.circuits[:]
        clone.max_willpower = self.max_willpower
        clone.hydro_spells = self.hydro_spells
        clone.abilities_gained_this_turn = self.abilities_gained_this_turn
        clone.distracted = self.distracted
        return clone

    def serialize(self) -> Dict:
        serialized = {'name': self.name, 'progress_dict': self.progress_dict.copy(), 'dev_plan': self.dev_plan[:],
                      'academics': self.academics, 'temperament': self.temperament, 'concept': self.concept,
                      'conditions': self.conditions[:], 'items': self.items, 'money': self.credits,
                      'willpower': self.willpower, 'bounty': self.bounty,
                      'relative_conditions': {k: v[:] for k, v in self.relative_conditions.items()},
                      'tattoo': self.tattoo, 'crafted_before': self.crafted_before}
        return serialized

    # Used for evaluating simulations
    def get_score(self) -> int:
        score = 0
        if self.is_dead():  # Explicitly unaware of resurrection, for better or worse
            score -= 100000000
        if self.has_condition(Condition.PETRIFIED):
            score -= 100
        if self.has_condition(Condition.CAUTERIZED):
            score -= 1000
        if self.has_condition(Condition.GRIEVOUS):
            score -= 100
        if self.has_condition(Condition.INJURED):
            score -= 10
        score += self.academics * 1000
        score += self.get_total_credit_value() * 2
        score += self.get_total_dev()
        return score

    def get_report(self):
        if get_main_report().aero_broadcast and self.has_condition(Condition.INTUITION):
            self.report += os.linesep + get_main_report().get_broadcasts(intuition=True,
                                                                         skip_combat=self.game.is_night()) + os.linesep

        if not self.game.is_day() and self.has_ability("Awareness I"):
            self.report += os.linesep
            night_combat_report = get_main_report().get_night_combat_report(self,
                                                                            intuition=self.has_condition(
                                                                                Condition.INTUITION))
            if not night_combat_report:
                night_combat_report = "The night was peaceful."
            if not night_combat_report.isspace():
                self.report += "You are Aware:" + os.linesep
            self.report += night_combat_report + os.linesep

        elif self.game.is_day() and get_combat_handler().wide_check and self.has_condition(Condition.INTUITION):
            self.report += os.linesep
            self.report += get_main_report().get_night_combat_report(self,
                                                                     intuition=self.has_condition(Condition.INTUITION))
            self.report += os.linesep

        if (self.game.is_day() or self.has_condition(Condition.NIGHT_LIGHT)) and self.has_ability("Awareness II"):
            training_count = 0
            training_report = "You are Aware:" + os.linesep
            for trainer in sorted(get_main_report().training.keys(), key=lambda x: x.name):
                hidden = False
                if trainer != self:
                    trained = get_main_report().training[trainer]
                    if trainer.has_condition(Condition.COUNTER_INT):
                        if trainer.has_condition(Condition.SUPER_COUNTER_INT) \
                                or not self.has_condition(Condition.PIERCE_COUNTER_INT):
                            if trainer.fake_ability:
                                trained = trainer.fake_ability.name
                            else:
                                trained = "nothing in particular"
                            if not isinstance(trainer.fake_action, Train) \
                                    and not (self.game.is_day() and isinstance(trainer.fake_action, Wander)):
                                hidden = True
                    if not hidden:
                        training_report += f"{trainer.name} was training {trained}." + os.linesep
                        training_count += 1
            if training_count:
                self.report += os.linesep
                self.report += training_report

        if (not self.game.is_day() or self.has_condition(Condition.PIERCE_ILLUSIONS)) \
                and self.has_condition(Condition.NIGHT_LIGHT):
            self.report += os.linesep
            self.report += get_main_report() \
                .get_personal_action_report(pierce_illusions=self.has_condition(Condition.PIERCE_ILLUSIONS),
                                            ignore_player=self,
                                            intuition=self.has_condition(Condition.INTUITION))
            self.report += os.linesep
        elif self.game.is_day() and self.has_condition(Condition.INTUITION):
            self.report += os.linesep
            self.report += get_main_report() \
                .get_action_report(pierce_illusions=self.has_condition(Condition.PIERCE_ILLUSIONS),
                                   ignore_player=self,
                                   intuition=self.has_condition(
                                       Condition.INTUITION),
                                   aero_only=True)
            self.report += os.linesep

        if self.has_ability("Attunement Detection"):
            self.report += os.linesep
            self.report += get_main_report().get_attunement_report(self)

        if self.has_ability("Willpower Detection"):
            self.report += os.linesep
            self.report += get_main_report().get_willpower_report(self)

        if self.has_ability("Market Connections I") or self.has_ability("Market Connections II"):
            self.report += os.linesep
            self.report += get_main_report().get_money_report(full=self.has_ability("Market Connections II"),
                                                              perspective_player=self)

        cleaned = self.report \
            .replace(COMBAT_PLACEHOLDER, get_main_report().get_combat_report_for_player(self)) \
            .replace(self.name + "'s", "your") \
            .replace(self.name, "you") \
            .replace("you has", "you have") \
            .replace("you was", "you were") \
            .replace("you is", "you are") \
            .replace("you healed themself", "you healed yourself") \
            .replace("you hurt themself", "you hurt yourself") \
            .replace("you succumbed to their", "you succumbed to your") \
            .replace("you tattooed themself", "you tattooed yourself") \
            .replace("your Poison Gas failed because they were Ambushed",
                     "your Poison Gas failed because you were Ambushed") \
            .replace("you animated their bunker",
                     "you animated your bunker") \
            .replace("your bunker collapsed around them",
                     "your bunker collapsed around you") \
            .replace("you held their sword",
                     "your held your sword") \
            .replace(f"Your intuition tells you this has to do with the concept {self.concept}.{os.linesep}", "") \
            .replace(f"Your intuition tells you this has to do with "
                     f"your Aeromancy ({self.concept}).{os.linesep}", "") \
            .replace(f"This unmistakably has to do with "
                     f"your Aeromancy ({self.concept}).{os.linesep}", "") \
            .replace("! you", "! You") \
            .replace(". you", ". You") \
            .replace("? you", "? You")

        if not self.has_ability("Fraud I") and not self.has_ability("Aeromancy Intuition"):
            cleaned = cleaned.replace(" (FAKE)", "")

        gather = []
        line_break = False
        for i in cleaned.split(os.linesep):
            if i.strip():
                line = i.strip()[0].upper()
                if len(i.strip()):
                    line += i.strip()[1:]
                gather.append(line)
                line_break = True
            elif line_break:
                gather.append("")
                line_break = False

        final = os.linesep.join(gather).replace("you while they", "you while you") \
            .replace("you (while they", "you (while you") \
            .replace("you were trying to heal themself", "you were trying to heal yourself") \
            .replace("you were trying to tattoo themself", "you were trying to tattoo yourself") \
            .replace("You expanded their mind", "You expanded your mind")

        if get_main_report().get_messages_for_player(self):
            final += os.linesep + get_main_report().get_messages_for_player(self)

        return final

    def is_dead(self):
        return Condition.DEAD in self.conditions

    @staticmethod
    def _validate_dev_plan(dev_plan, complete_ability_pins, name):
        for ability_pin in dev_plan:
            if (ability_pin % 100 + 300 if ability_pin > 700 else ability_pin) == CONCEPT_I:
                raise Exception(
                    f"Player {name} is trying to learn Concept I without starting with it.")
            if ability_pin == LEGACY_MAGIC:
                raise Exception(
                    f"Player {name} is trying to learn Legacy Magic without starting with it.")
            ability = get_ability(ability_pin)

            if ability_pin in complete_ability_pins:
                raise Exception(
                    f"Player {name} already has dev plan ability {ability.name}")

            if ability_pin == LEGACY_MAGIC:
                legacy_prereqs = [
                    pin for pin in complete_ability_pins if pin in range(601, 10001, 100)]
                if not len(legacy_prereqs):
                    raise Exception(f"Player {name} is missing prerequisite "
                                    f"for ability {ability.name}")
            elif ability_pin == REALITY_IMPOSITION:
                legacy_prereqs = [
                    pin for pin in complete_ability_pins if pin in range(603, 10003, 100)]
                if not len(legacy_prereqs):
                    raise Exception(f"Player {name} is missing prerequisite "
                                    f"for ability {ability.name}")
            elif ability.prerequisite_pin and ability.prerequisite_pin not in complete_ability_pins:
                raise Exception(f"Player {name} is missing prerequisite "
                                f"for dev plan ability {ability.name} ({ability.get_prerequisite().name})")
            complete_ability_pins.append(ability_pin)

    def set_dev_plan(self, *ability_names: str):
        self.dev_plan = [get_ability_by_name(
            ability).pin for ability in ability_names]
        complete_ability_pins = [
            ability.pin for ability in self.get_abilities()]
        self._validate_dev_plan(
            self.dev_plan, complete_ability_pins, self.name)

    def _generic_action_check(self, bonus=False, day_only=False):
        if self.is_dead():
            raise Exception(f"Player {self.name} is DEAD and cannot act.")
        if bonus:
            if self.bonus_action:
                raise Exception(
                    f"Player {self.name} is already taking a bonus.")
            self.distracted = True
        else:
            if not isinstance(self.action, Wander):
                raise Exception(
                    f"Player {self.name} is already taking an action.")
        if day_only:
            if not self.game.is_day():
                raise Exception(
                    f"Player {self.name} is trying to take a day only action at night.")

    # For turning off Petrify and the like
    def disable_ability(self, ability_name: str):
        if ability_name.upper() not in ("PETRIFICATION I", "STEALTH RESURRECTION", "REALITY IMPOSITION",
                                        "ARMOR BREAK", "SABOTAGE"):
            # Case by case basis
            raise Exception(f"Not toggleable ability? {ability_name}")
        self.disabled_ability_pins.add(get_ability_by_name(ability_name).pin)

    def plan_fake_ability(self, ability: Union[Ability, str]):
        if isinstance(ability, str):
            ability = get_ability_by_name(ability)
        self.fake_ability = ability

    def plan_fake_action(self, action: 'Action'):
        self.fake_action = action

    def plan_class(self):
        self._generic_action_check(day_only=True)
        self.action = Class(self.game, self)

    def plan_doctor(self):
        self._generic_action_check(day_only=True)
        self.action = Doctor(self.game, self)

    def plan_bounty(self, target: "Player", amount: int):
        assert amount >= 1
        if target not in self.bounties_placed:
            PlaceBounty(self.game, self, target, amount)
            self.bounties_placed.add(target)

    def plan_shop(self, *item_names, automata_name: Union[Optional[List[str]], str] = None):
        if not automata_name:
            automata_name = []
        if not isinstance(automata_name, list):
            automata_name = [automata_name]

        self._generic_action_check(day_only=True)
        item_names_to_amount = {}
        for item_name in item_names:
            if item_name not in item_names_to_amount:
                item_names_to_amount[item_name] = 0
            item_names_to_amount[item_name] += 1

        items = {get_item_by_name(item_name): amount for (
            item_name, amount) in item_names_to_amount.items()}

        for item in items:
            if item.cost < 0:
                raise Exception(
                    f"Player {self.name} is trying to buy an item that is not for sale {item.name}.")

        # if Shop.get_total_cost(items) > self.get_credits():
        #     raise Exception(f"Player {self.name} is trying to buy more than they can afford.")
        self.action = Shop(self.game, self, items,
                           automata_names=automata_name)

    def plan_train(self):
        self._generic_action_check()
        self.action = Train(self.game, self)

    def plan_bunker(self, bonus=False):
        self._generic_action_check(bonus=bonus)
        if bonus:
            self.bonus_action = Bunker(self.game, self, bonus=bonus)
        else:
            self.action = Bunker(self.game, self, bonus=bonus)

    def plan_attack(self, *targets: "Player"):
        self._generic_action_check()
        if len(targets) != len(set(targets)):
            raise Exception(
                f"Player {self.name} is trying to attack the same enemy multiple times.")
        if len(targets) > 3:
            raise Exception(
                f"Player {self.name} is trying to attack too many enemies.")
        for target in targets:
            if target.name == self.name:
                raise Exception(
                    f"Player {self.name} is trying to attack themselves.")
        filtered_targets = [
            target for target in targets if not target.is_dead()]
        if filtered_targets:
            if len(filtered_targets) == 1:
                self.action = Attack(self.game, self, filtered_targets[0])
            else:
                self.action = MultiAttack(self.game, self, filtered_targets)

    # Will fail if the target is dead or if player isn't a healer
    def plan_heal(self, target: "Player", bonus=False):
        self._generic_action_check(bonus=bonus)
        if bonus:
            self.bonus_action = Heal(self.game, self, target, True)
        else:
            self.action = Heal(self.game, self, target)

    def plan_teach(self, target: "Player", ability_name: str):
        self._generic_action_check()
        ability = get_ability_by_name(ability_name)
        if ability not in self.get_abilities():
            raise Exception(
                f"Player {self.name} is trying to teach an ability they don't have ({ability_name}).")
        self.action = Teach(self.game, self, target, ability)

    def plan_learn(self, target: "Player"):
        self._generic_action_check()
        self.action = Learn(self.game, self, target)

    def plan_steal(self, target: "Player"):
        self._generic_action_check()
        self.action = Steal(self.game, self, target)

    def plan_spy(self, *targets: "Player"):
        self._generic_action_check(bonus=True)
        max_targets = 1
        if self.has_ability("Awareness III"):
            max_targets += 1
        if len(targets) > max_targets:
            raise Exception(
                f"Player {self.name} is trying to spy on too many targets.")
        for target in targets:
            if target == self:
                raise Exception(
                    f"Player {self.name} is trying to spy on themself.")
            # It doesn't matter this overwrites. We just need at least one set to the Class
            self.bonus_action = Spy(self.game, self, target)

    def plan_blackmail(self, target: 'Player', message: str):
        if target in self.blackmail_placed:
            raise Exception(
                f"Player {self.name} is trying to blackmail {target.name} multiple times.")
        self.blackmail_placed.add(target)
        if not self.check_relative_condition(target, Condition.HOOK):
            raise Exception(
                f"Player {self.name} is trying to blackmail {target.name} when they don't have a hook.")
        Blackmail(self.game, self, target, message)

    def plan_taunt(self, target: 'Player', message: str = ""):
        if target in self.taunt_placed:
            raise Exception(
                f"Player {self.name} is trying to taunt {target.name} multiple times.")
        self.taunt_placed.add(target)
        if not self.check_relative_condition(target, Condition.TAUNT):
            raise Exception(
                f"Player {self.name} is trying to taunt {target.name} when they don't have a taunt.")
        Taunt(self.game, self, target, message)

    def plan_consume_item(self, *item_names: 'str', ignore_possession_check=False):
        if self.consuming:
            raise Exception(
                f"Player {self.name} is trying to consume multiple times.")
        self.consuming = True
        for item_name in item_names:
            item = get_item_by_name(item_name)
            if item.pin in CONSUME_PREFER:
                if CONSUME_PREFER[item.pin] in self.items:
                    item = get_item(CONSUME_PREFER[item.pin])
            if not ignore_possession_check and item.pin not in self.items:
                raise Exception(
                    f"Player {self.name} is trying to use an item they don't have ({item_name}).")
            if item.item_type not in [ItemType.CONSUMABLE, ItemType.POTION]:
                raise Exception(
                    f"Player {self.name} is trying to use an item that isn't consumable ({item_name}).")
            # Constructor adds it to the action queue
            ConsumeItem(self.game, self, item)

    def plan_trade(self, target: "Player", money: int = 0, item_names: Optional[List[str]] = None,
                   automata: Union[Optional[List[Union['Automata', str]]],
                                   'Automata', str] = None,
                   action_condition: Optional[Union[ACTION_CONDITION, Tuple['Player', Type['Action']],
                                                    Tuple['Player', Type['Action'], 'Player']]] = None,
                   item_name_condition: Optional[Tuple["Player", int, List[str]]] = None):
        assert target != self
        if action_condition:
            if len(action_condition) == 2:
                action_condition = (
                    action_condition[0], action_condition[1], None, True)
            elif len(action_condition) == 3:
                action_condition = (
                    action_condition[0], action_condition[1], action_condition[2], True)
        items: Optional[Dict['Item', int]] = None
        if item_names is not None:
            item_names_to_amount = {}
            for item_name in item_names:
                if item_name not in item_names_to_amount:
                    item_names_to_amount[item_name] = 0
                item_names_to_amount[item_name] += 1

            items = {get_item_by_name(item_name): amount for (
                item_name, amount) in item_names_to_amount.items()}
            for item in items.keys():
                if item.stuck:
                    raise Exception(
                        f"Player {self.name} is trying to ditch an untradeable item {item.name}.")

        if automata and not isinstance(automata, list):
            automata = [automata]

        item_condition: Optional[ITEM_CONDITION] = None
        if item_name_condition is not None:
            item_names_to_amount = {}
            for item_name in item_name_condition[2]:
                if item_name not in item_names_to_amount:
                    item_names_to_amount[item_name] = 0
                item_names_to_amount[item_name] += 1

            item_condition = (item_name_condition[0], item_name_condition[1],
                              {get_item_by_name(item_name): amount for (item_name, amount) in
                               item_names_to_amount.items()})

        Trade(self.game, self, target, items, money,
              automata, action_condition, item_condition)

    def plan_face_mask(self, player: 'Player'):
        if self.masking:
            raise Exception(
                f"Player {self.name} is trying to mask multiple times.")
        self.masking = True
        if self.game.is_day():
            raise Exception(
                f"Player {self.name} is trying to use a Face Mask in broad daylight.")
        if FACE_MASK not in self.items:
            raise Exception(
                f"Player {self.name} is trying to use a Face Mask without owning one.")
        Disguise(self.game, self, player)

    def plan_attune(self, *elements: Element):
        if self.attuning:
            raise Exception(
                f"Player {self.name} is trying to attune multiple times.")
        if len(elements):
            self.attuning = True
            Attune(self.game, self, tuple(elements))

    def plan_hydro(self, ability_name: str, will: Union[Optional[List[int]], int] = None, contingency: bool = False,
                   targets: Union[Optional[List['Player']], 'Player'] = None):
        if isinstance(will, int):
            will = [will]

        if not targets:
            targets = []
        if not isinstance(targets, list):
            targets = [targets]

        assert self.has_ability(ability_name, strict=True), f"Player {self.name} is trying to cast " \
                                                            f"an ability they don't know {ability_name}."
        ability = get_ability_by_name(ability_name)
        assert not contingency or not ability.contingency_forbidden, f"Player {self.name} is trying to use a " \
                                                                     f"contingency that is forbidden ({ability_name})."
        assert len(ability.hydro_qualified_skills), f"Player {self.name} is trying to cast " \
                                                    f"a non hydro ability {ability_name}."
        if not will:
            if len(ability.hydro_qualified_skills) == 1 or ability.linked:
                if not ability.hydro_qualified_skills[0].each:
                    will = [ability.hydro_qualified_skills[0].cost]
            else:
                will = []

        if not ability.linked and len(will) != len(ability.hydro_qualified_skills):
            raise Exception(
                f"Player {self.name} mismatch with {ability_name} ({will}).")
        if ability.linked and not will:
            raise Exception(
                f"Player {self.name} mismatch with {ability_name} ({will}).")
        for i in range(len(will)):
            if will[i] < 0 or will[i] > ability.hydro_qualified_skills[i].cost:
                raise Exception(
                    f"Player {self.name} mismatch with {ability_name} ({will}).")
        if sum(will) > ability.max_will:
            raise Exception(
                f"Player {self.name} is trying to spend too much willpower on {ability_name} ({will}).")

        if targets:
            assert len(targets) <= ability.max_targets
            self.ability_targets[ability.pin] = targets

        UseHydro(self.game, self, ability, will, contingency)

        if ability.name == "Illusions III":
            assert len(targets) == 3 == len(set(targets))
            MasterIllusion(
                self.game, self, target=targets[0], defended=targets[1], redirected=targets[2])

    def plan_target(self, ability_name: str, *targets: "Player"):
        ability = get_ability_by_name(ability_name)
        assert len(targets) <= ability.max_targets
        if ability.target_other:
            assert self not in targets
        self.ability_targets[ability.pin] = list(targets)

    def plan_item_target(self, item_name, *targets: "Player"):
        item = get_item_by_name(item_name)
        self.item_targets[item.pin] = list(targets)

    def plan_tattoo_target(self, *targets: "Player"):
        self.tattoo_targets = list(targets)

    def plan_ability_choose(self, ability_name: str, choice: int, for_rune=False, for_tattoo=False):
        ability = get_ability_by_name(ability_name)
        assert choice >= 0
        if ability.must_choose:
            assert choice < ability.must_choose
        if for_rune:
            self.item_choices[get_item_by_name(
                ability_name + " rune").pin] = choice
        if for_tattoo:
            self.tattoo_choice = choice
        else:
            self.ability_choices[ability.pin] = choice

    def plan_illusion(self, target: 'Player', action: 'Action', ability: Optional[str] = None):
        assert not self.used_illusion

        if ability:
            Illusion(self.game, self, target=target, fake_action=action,
                     fake_training=get_ability_by_name(ability))
        else:
            Illusion(self.game, self, target=target, fake_action=action)

        self.used_illusion = True

    def plan_craft(self, *item_names, automata_name: Union[Optional[List[str]], str] = None, shackle: bool = True):
        if not automata_name:
            automata_name = []
        if not isinstance(automata_name, list):
            automata_name = [automata_name]

        self._generic_action_check()
        item_names_to_amount = {}
        for item_name in item_names:
            if item_name not in item_names_to_amount:
                item_names_to_amount[item_name] = 0
            item_names_to_amount[item_name] += 1

        items = {get_item_by_name(item_name): amount for (
            item_name, amount) in item_names_to_amount.items()}

        self.action = Craft(self.game, self, items,
                            automata_names=automata_name, shackle=shackle)

    def plan_craft_rune(self, ability_name: str, bonus=False):
        self._generic_action_check(bonus=bonus)
        items = {get_item_by_name(ability_name + " Rune"): 1}
        if bonus:
            self.bonus_action = Craft(self.game, self, items, is_bonus=True)
        else:
            self.action = Craft(self.game, self, items)

    def plan_tattoo(self, target: 'Player', ability_name: str):
        self._generic_action_check()
        rune = get_item_by_name(ability_name + " Rune")
        assert isinstance(rune, Rune)
        self.action = Tattoo(self.game, self, target, rune)

    def plan_get_tattoo(self, target: 'Player'):
        self.action = Canvas(self.game, self, target)

    def plan_send_message(self, targets: List['Player'], message: str):
        self.message_count += 1
        assert self.message_count <= 3
        assert len(message) < 350
        assert len(targets) <= 5
        SendMessage(self.game, self, targets, message)

    def get_awareness(self):
        awareness = 0
        if self.has_ability("Awareness I"):
            awareness += 1
        if self.has_ability("Awareness II"):
            awareness += 1
        if self.has_ability("Awareness III"):
            awareness += 1
        if self.has_ability("Panopticon"):
            awareness += 1
        return awareness

    def has_ability(self, ability_name: str, strict=False, ignore_this_turn=True):
        ability = get_ability_by_name(ability_name)
        if not strict:
            if ability.pin in self.temporary_abilities:
                return True
        if ignore_this_turn:
            if ability.pin in self.abilities_gained_this_turn:
                return False
        return ability.pin in self.progress_dict and self.progress_dict[ability.pin] >= ability.cost

    def get_abilities(self, include_this_turn: bool = False) -> List[Ability]:
        abilities = []
        for (ability_pin, progress) in self.progress_dict.items():
            if include_this_turn or ability_pin not in self.abilities_gained_this_turn:
                ability = get_ability(ability_pin)
                if progress >= ability.cost:
                    abilities.append(ability)
        return abilities

    def get_partial_abilities(self) -> List[Tuple[Ability, int]]:
        abilities = []
        for (ability_pin, progress) in self.progress_dict.items():
            ability = get_ability(ability_pin)
            if progress < ability.cost:
                abilities.append((ability, progress))
        return abilities

    def get_total_dev(self) -> int:
        total = 0
        for (ability_pin, progress) in self.progress_dict.items():
            total += progress
        return total

    def _check_attunement(self, attunement: Tuple[Element, ...]) -> bool:
        total_circuits = (self.conditions +
                          self.turn_conditions).count(Condition.CIRCUIT)
        max_anti = (self.conditions +
                    self.turn_conditions).count(Condition.ANTI_CIRCUIT)
        max_fire = (self.conditions +
                    self.turn_conditions).count(Condition.FIRE_CIRCUIT)
        max_water = (self.conditions +
                     self.turn_conditions).count(Condition.WATER_CIRCUIT)
        max_earth = (self.conditions +
                     self.turn_conditions).count(Condition.EARTH_CIRCUIT)
        max_air = (self.conditions +
                   self.turn_conditions).count(Condition.AIR_CIRCUIT)
        max_light = (self.conditions +
                     self.turn_conditions).count(Condition.LIGHT_CIRCUIT)
        max_warp = (self.conditions +
                    self.turn_conditions).count(Condition.WARP_CIRCUIT)
        max_gold = (self.conditions +
                    self.turn_conditions).count(Condition.GOLD_CIRCUIT)

        if len(attunement) > total_circuits:
            return False
        if attunement.count(Element.ANTI) > max_anti:
            return False
        if attunement.count(Element.FIRE) > max_fire:
            return False
        if attunement.count(Element.WATER) > max_water:
            return False
        if attunement.count(Element.EARTH) > max_earth:
            return False
        if attunement.count(Element.AIR) > max_air:
            return False
        if attunement.count(Element.LIGHT) > max_light:
            return False
        if attunement.count(Element.WARP) > max_warp:
            return False
        if attunement.count(Element.GOLD) > max_gold:
            return False

        return True

    # Returns if attunement was legal. Only sets if legal
    def set_attunement(self, attunement: Tuple[Element, ...]) -> bool:
        if self._check_attunement(attunement):
            self.circuits = attunement[:]
            return True

        return False

    def get_one_swap_attunement(self) -> List[Tuple[Element, ...]]:
        possibilities = {tuple(self.circuits)}
        if self.circuits:
            for i in range(len(list(self.circuits))):
                for element in Element:
                    possibility = tuple(
                        self.circuits[:i]) + (element,) + tuple(self.circuits[i + 1:])
                    possibilities.add(possibility)
        for element in Element:
            possibilities.add(tuple(self.circuits[:]) + (element,))

        return [possibility for possibility in possibilities if self._check_attunement(possibility)]

    def get_possible_attunement(self) -> List[Tuple[Element, ...]]:
        all_possibilities: List[Tuple[Element, ...]] = []
        total_circuits = (self.conditions +
                          self.turn_conditions).count(Condition.CIRCUIT)

        def legal_attunement(attunement: Tuple[Element, ...]):
            return self._check_attunement(attunement)

        for i in range(total_circuits + 1):
            possibilities = itertools.combinations_with_replacement([Element.ANTI, Element.FIRE, Element.WATER,
                                                                     Element.EARTH, Element.AIR, Element.LIGHT,
                                                                     Element.WARP, Element.GOLD], i)
            all_possibilities.extend(filter(legal_attunement, possibilities))

        return all_possibilities

    def get_items(self, duplicates=True) -> List[Item]:
        if duplicates:
            return [get_item(pin) for pin in self.items]
        item_set = set(self.items)
        return [get_item(pin) for pin in item_set]

    def get_items_display(self) -> Dict[str, int]:
        sorted_items = sorted(set(self.items), key=lambda x: get_item(x).cost)
        return [(get_item(pin).name, self.items.count(pin)) for pin in sorted_items] + [("Credits", self.credits)]

    def get_total_credit_value(self) -> int:
        total = self.credits
        for item in self.get_items():
            total += abs(item.cost)
        return total

    def get_consumed_items(self) -> List[Item]:
        return [get_item(pin) for pin in self.consumed_items]

    def get_held_weapon(self) -> Optional[Item]:
        # Get the most expensive item
        best: Optional[Item] = None
        cost = -100
        for item in self.get_items(False):
            if item.item_type == ItemType.WEAPON:
                if abs(item.cost) > cost:
                    best = item
                    cost = abs(item.cost)
        return best

    def get_worn_armor(self) -> Optional[Item]:
        # Get the most expensive item
        best: Optional[Item] = None
        cost = -100
        for item in self.get_items(False):
            if item.item_type == ItemType.ARMOR:
                if item.cost > cost:
                    best = item
                    cost = item.cost
        return best

    def _get_non_consumable_item_skills(self) -> List[Skill]:
        skills = []
        for item in self.get_items(duplicates=False):
            if item.item_type not in [ItemType.CONSUMABLE, ItemType.POTION] and not item.stacking:
                skills += item.get_skills()
        for item in self.get_items(duplicates=True):
            if item.item_type not in [ItemType.CONSUMABLE, ItemType.POTION] and item.stacking:
                skills += item.get_skills()
        return skills

    def get_skills(self, include_this_turn: bool = False) -> List[Skill]:
        skills = []
        for ability in self.get_abilities(include_this_turn):
            if ability.pin not in self.disabled_ability_pins:
                ability_skills = ability.get_skills(self.circuits, self.hydro_spells.get(ability.pin, []),
                                                    choice=self.ability_choices.get(ability.pin, -1))
                if ability.pin in self.ability_targets:
                    for skill in ability_skills:
                        if skill.trigger == Trigger.TARGET:
                            skill.targets = self.ability_targets[ability.pin]
                skills += ability_skills
        skills += self._get_non_consumable_item_skills()
        for item in self.get_consumed_items():
            # Dimensional Key is special since it gets consumed BEFORE the non combat skill, so we exclude it here
            if item.pin != DIMENSIONAL_KEY:
                skills += item.get_skills(choice=self.item_choices.get(item.pin, -1),
                                          targets=self.item_targets.get(item.pin, []))
        skills += self.temporary_skills
        if self.has_ability("Reinforced Will"):
            for skill in skills:
                if skill.fragile:
                    skill.set_fragile(False)
        return skills

    def get_fake_temperament(self):
        seed = self.game.seed if self.game else 0
        h = int(''.join(map(lambda x: '%.3d' % ord(x), self.name))) + seed
        possible = [e for e in Temperament if e not in [
            Temperament.NONE, Temperament.PREPARED, Temperament.PARANOIAC, self.temperament]]
        return possible[h % len(possible)]

    def has_prerequisite(self, ability: Ability) -> bool:
        if ability.pin == 307:
            for ability_pin in self.progress_dict.keys():
                if ability_pin >= 600:
                    if ability_pin % 100 == 3:
                        if self.has_ability(get_ability(ability_pin).name, strict=True):
                            return True
            return False
        prerequisite = ability.get_prerequisite()
        if not prerequisite:
            return True
        return self.has_ability(prerequisite.name, strict=True)

    def has_condition(self, condition: Condition) -> bool:
        return condition in (self.conditions + self.turn_conditions + self.tentative_conditions)

    def check_relative_condition(self, player: 'Player', condition: Condition) -> bool:
        return condition in self.relative_conditions.get(player.name, [])

    def add_relative_condition(self, player: 'Player', condition: Condition, duplicate=False) -> bool:
        if player.name not in self.relative_conditions:
            self.relative_conditions[player.name] = []
        if duplicate or condition not in self.relative_conditions[player.name]:
            self.relative_conditions[player.name].append(condition)
            return True
        return False

    def remove_relative_condition(self, player: 'Player', condition: Condition):
        if player.name in self.relative_conditions and condition in self.relative_conditions[player.name]:
            self.relative_conditions[player.name].remove(condition)

    def relative_condition_debug(self) -> List[str]:
        results = []
        for k, v in self.relative_conditions.items():
            for c in v:
                results.append(f"{k}_{c.name}")
        return results

    def condition_debug(self) -> Dict[str, int]:
        results = [condition.name for condition in self.conditions]
        results = sorted(results)
        results.extend(self.relative_condition_debug())
        results_map = {}
        for result in results:
            if result not in results_map:
                results_map[result] = 0
            results_map[result] += 1
        return results_map

    def total_progress(self) -> int:
        total = 0
        for progress in self.progress_dict.values():
            total += progress
        return total

    def gain_progress(self, progress: int) -> NoReturn:
        if self.is_dead():
            return
        self.report += f'+{progress} Progress{os.linesep}'

        while progress > 0:
            if len(self.dev_plan) == 0:
                self.report += f"You failed to set sufficient dev goals, " \
                               f"so {progress} Progress has been wasted.{os.linesep}"
                return
            ability_pin = self.dev_plan[0]
            ability = get_ability(ability_pin)
            needed = ability.cost
            if ability_pin in self.progress_dict:
                needed -= self.progress_dict[ability_pin]

            if progress >= needed:
                progress -= needed
                self.gain_ability(ability)
            else:
                if ability_pin not in self.progress_dict:
                    self.progress_dict[ability_pin] = 0
                self.progress_dict[ability_pin] += progress

                self.report += f'{ability.name} ({self.progress_dict[ability_pin]}/{ability.cost}){os.linesep}'
                progress = 0

    def gain_ability(self, ability: Ability) -> NoReturn:
        self.report += f'You have gained {ability.name}{os.linesep}'
        self.progress_dict[ability.pin] = ability.cost
        self.abilities_gained_this_turn.append(ability.pin)
        if ability.pin in self.dev_plan:
            self.dev_plan.remove(ability.pin)
        for skill in ability.get_skills(self.circuits, self.hydro_spells.get(ability.pin, [])):
            if skill.trigger == Trigger.ACQUISITION:
                HandleSkill(self.game, self, skill)

    def copycat(self, target: 'Player', fake: 'bool' = False) -> NoReturn:
        available_abilities = [ability for ability in target.get_abilities()
                               if ability.is_copyable() and
                               not self.has_ability(ability.name, strict=True, ignore_this_turn=False) and
                               self.has_prerequisite(ability)]
        available_abilities.sort()
        if not fake and available_abilities:
            self.gain_ability(available_abilities[0])
        else:
            self.report += "There was nothing to copy." + os.linesep

    def dev_sabotaged(self, message_if_destroyed: str) -> NoReturn:
        potential_sabotage_abilities = []
        for ability_pin, progress in self.progress_dict.items():
            ability = get_ability(ability_pin)
            if 0 < progress < ability.cost:
                potential_sabotage_abilities.append(ability)
        potential_sabotage_abilities.sort()
        #  Prioritize the first item in the dev plan
        if self.dev_plan:
            first_ability = get_ability(self.dev_plan[0])
            if first_ability in potential_sabotage_abilities:
                potential_sabotage_abilities.remove(first_ability)
                potential_sabotage_abilities.insert(0, first_ability)
        if potential_sabotage_abilities:
            sabotaged = potential_sabotage_abilities[0]
            self.report += message_if_destroyed + os.linesep
            self.report += f"You have lost {self.progress_dict[sabotaged.pin]} progress towards {sabotaged.name}." \
                           + os.linesep
            self.progress_dict[sabotaged.pin] = 0

    def _non_combat_report_callable(self) -> ReportCallable:
        def report_callable(message: str, info_scope: InfoScope):
            if self.game.simulation:
                return
            if info_scope == InfoScope.HIDDEN:
                return
            self.report += message + os.linesep
            if info_scope == InfoScope.PUBLIC:
                get_main_report().add_action(self, message)
            if info_scope == InfoScope.BROADCAST:
                get_main_report().broadcast(message)

        return report_callable

    def die(self, message, reporting_func: Optional[ReportCallable] = None):
        if not reporting_func:
            reporting_func = self._non_combat_report_callable()
        if self.temperament == Temperament.STUBBORN:
            if not self.has_condition(Condition.PETRIFIED):
                if self.conditions.count(Condition.STUBBORN) < 3:
                    self.conditions.append(Condition.STUBBORN)
                    reporting_func(f"{self.name} stubbornly clung to life.", InfoScope.PUBLIC)
                    return
        self.conditions.append(Condition.DEAD)
        Action.handle_death_triggers(self.game, self)
        if self.has_condition(Condition.RESURRECT):
            Resurrect(self.game, self, self.has_condition(
                Condition.STEALTH_REZ))
            if self.has_condition(Condition.STEALTH_REZ):
                reporting_func(message, InfoScope.BROADCAST)
                get_main_report().add_death(self)
            else:
                reporting_func(message, InfoScope.PUBLIC)
        else:
            reporting_func(message, InfoScope.BROADCAST)
            get_main_report().add_death(self)

    def kill(self, reporting_func: Optional[ReportCallable] = None):
        if reporting_func is None:
            reporting_func = self._non_combat_report_callable()

        if LIZARD_TAIL in self.items:
            reporting_func(
                f"{self.name} used a Lizard Tail to avoid being wounded.", InfoScope.PUBLIC)
            self.items.remove(LIZARD_TAIL)
            reporting_func(
                f"Lizard Tail consumed ({self.items.count(LIZARD_TAIL)} remaining).", InfoScope.PRIVATE)
            return False

        self.die(f"{self.name} died.", reporting_func)
        return True

    def wound(self, injury_modifiers: Optional[List[InjuryModifier]] = None,
              reporting_func: Optional[ReportCallable] = None) -> bool:
        if injury_modifiers is None:
            injury_modifiers = []
        if reporting_func is None:
            reporting_func = self._non_combat_report_callable()

        if LIZARD_TAIL in self.items:
            if InjuryModifier.NONLETHAL not in injury_modifiers or Condition.INJURED not in self.conditions:
                reporting_func(
                    f"{self.name} used a Lizard Tail to avoid being wounded.", InfoScope.PUBLIC)
                self.items.remove(LIZARD_TAIL)
                reporting_func(
                    f"Lizard Tail consumed ({self.items.count(LIZARD_TAIL)} remaining).", InfoScope.PRIVATE)
                return False

        if Condition.DEAD not in self.conditions:
            if Condition.INJURED in self.conditions:
                if InjuryModifier.NONLETHAL not in injury_modifiers:
                    self.die(f"{self.name} died.", reporting_func)
                    return True
            else:
                if InjuryModifier.GRIEVOUS in injury_modifiers:
                    self.conditions.append(Condition.GRIEVOUS)
                    if InjuryModifier.PERMANENT in injury_modifiers:
                        self.conditions.append(Condition.CAUTERIZED)
                        reporting_func(
                            f"{self.name} was permanently grievously injured.", InfoScope.PRIVATE)
                    else:
                        reporting_func(
                            f"{self.name} was grievously injured.", InfoScope.PRIVATE)
                else:
                    if InjuryModifier.PERMANENT in injury_modifiers:
                        self.conditions.append(Condition.CAUTERIZED)
                        reporting_func(
                            f"{self.name} was permanently injured.", InfoScope.PRIVATE)
                    else:
                        reporting_func(
                            f"{self.name} was injured.", InfoScope.PRIVATE)
                self.conditions.append(Condition.INJURED)
                return True
        return False

    def petrify(self, reporting_func: Optional[ReportCallable] = None, mini=False, long=False):
        if Condition.DEAD in self.conditions:
            return

        if reporting_func is None:
            reporting_func = self._non_combat_report_callable()

        if Condition.PETRIFIED not in self.conditions:
            if self.has_condition(Condition.PETRIFY_IMMUNE):
                reporting_func(
                    f"{self.name} was unaffected by petrification.", InfoScope.PUBLIC)
                return
            if SOFT in self.items:
                reporting_func(
                    f"{self.name} used a Soft to avoid being petrified.", InfoScope.PUBLIC)
                self.items.remove(SOFT)
                reporting_func(
                    f"Soft consumed ({self.items.count(SOFT)} remaining).", InfoScope.PRIVATE)
                return

            reporting_func(f"{self.name} was Petrified.", InfoScope.PUBLIC)
        # Reset Petrification Counter
        timer = 2
        if long:
            timer = 3
        if mini:
            timer = 1
        while self.conditions.count(Condition.PETRIFIED) < timer:
            self.conditions.append(Condition.PETRIFIED)

    # Returns true if still injured
    def heal(self) -> bool:
        if Condition.CAUTERIZED in self.conditions:
            # If permanently injured, you can reset the counter on grievous, otherwise does nothing
            if Condition.GRIEVOUS in self.conditions:
                for i in range(self.conditions.count(Condition.GRIEVOUS) - 1):
                    self.conditions.remove(Condition.GRIEVOUS)
        elif Condition.GRIEVOUS in self.conditions:
            while Condition.GRIEVOUS in self.conditions:
                self.conditions.remove(Condition.GRIEVOUS)
        elif Condition.INJURED in self.conditions:
            self.conditions.remove(Condition.INJURED)
        return Condition.INJURED in self.conditions

    def get_credits(self):
        return self.credits

    def gain_credits(self, amount):
        self.credits += amount

    def lose_credits(self, amount):
        self.credits -= amount

    def gain_item(self, item: Item, amount=1):
        if item.pin == AUTOMATA:
            raise Exception("Something went wrong with Automata.")
        for i in range(amount):
            self.items.append(item.pin)
        self.report += f"{item.name} x{amount} gained ({self.items.count(item.pin)} total)" + \
            os.linesep

    def lose_item(self, item: Item, amount=1):
        for i in range(amount):
            self.items.remove(item.pin)
        self.report += f"{item.name} x{amount} lost ({self.items.count(item.pin)} remaining)" + \
            os.linesep

    def destroy_fragile_items(self, include_loot: bool = False):
        lost_items = {}
        for item in self.get_items(duplicates=True):
            if item.fragile or (include_loot and item.loot):
                if item.pin not in lost_items:
                    lost_items[item.pin] = 0
                lost_items[item.pin] += 1
        for item_pin, amount in lost_items.items():
            self.lose_item(get_item(item_pin), amount)

    def destroy_consumables_and_reactives(self):
        lost_items = {}
        for item in self.get_items(duplicates=True):
            if item.item_type in [ItemType.CONSUMABLE, ItemType.REACTIVE, ItemType.POTION]:
                if item.pin not in lost_items:
                    lost_items[item.pin] = 0
                lost_items[item.pin] += 1
        for item_pin, amount in lost_items.items():
            self.lose_item(get_item(item_pin), amount)
