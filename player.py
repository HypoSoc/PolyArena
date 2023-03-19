import itertools
import os
from typing import Dict, List, NoReturn, Optional, Set, Tuple, Type, Union, Iterable

from ability import get_ability, Ability, get_ability_by_name
from actions import Action, Wander, Class, Train, Bunker, Attack, ConsumeItem, Doctor, Teach, Learn, Heal, Shop, \
    ITEM_CONDITION, Trade, ACTION_CONDITION, Disguise, Spy, Blackmail, Steal, Attune, Craft, Tattoo, Canvas, MultiAttack
from constants import Temperament, Condition, ItemType, InjuryModifier, InfoScope, COMBAT_PLACEHOLDER, Element
from game import Game
from items import Item, get_item, get_item_by_name, Rune
from report import ReportCallable, DayReport
from skill import Skill


FACE_MASK = get_item_by_name("Face Mask").pin
LIZARD_TAIL = get_item_by_name("Lizard Tail").pin
MEDKIT = get_item_by_name("Medkit").pin
DEPLETED_MEDKIT = get_item_by_name("1/2 Medkit").pin
SOFT = get_item_by_name("Soft").pin

CONSUME_PREFER = {MEDKIT: DEPLETED_MEDKIT}


class Player:
    def __init__(self, name: str, progress_dict: Dict[int, int], dev_plan: List[int], academics: int,
                 temperament: Temperament, conditions: List[Condition], items: List[int], money: int,
                 relative_conditions: Dict[str, List[Condition]], tattoo: Optional[int],
                 game: Game):
        assert "%" not in name, "Illegal character %"

        self.name = name
        self.progress_dict = progress_dict
        self.academics = academics
        self.temperament = temperament
        self.items = items
        self.conditions = conditions
        self.credits = money
        self.relative_conditions = relative_conditions  # Used for Hooks, Know thy enemy, and aeromancy
        self.tattoo = tattoo  # Rune item pin
        self.game = game

        self.consuming = False
        self.masking = False
        self.attuning = False

        complete_ability_pins = [None]
        for (ability_pin, progress) in progress_dict.items():
            ability = get_ability(ability_pin)
            if progress < 0 or progress > ability.cost:
                raise Exception(f"Player {name} has an illegal progress value "
                                f"{progress} for {ability.name} ({ability_pin})")
            if progress == ability.cost:
                complete_ability_pins.append(ability_pin)

        for (ability_pin, progress) in progress_dict.items():
            ability = get_ability(ability_pin)
            if progress > 0 and ability.prerequisite_pin not in complete_ability_pins:
                raise Exception(f"Player {name} is missing prerequisite "
                                f"for ability {ability.name} ({ability.get_prerequisite().name})")

        self.dev_plan = dev_plan

        for ability_pin in dev_plan:
            ability = get_ability(ability_pin)
            if ability_pin in complete_ability_pins:
                raise Exception(f"Player {name} already has dev plan ability {ability.name}")
            if ability.prerequisite_pin not in complete_ability_pins:
                raise Exception(f"Player {name} is missing prerequisite "
                                f"for dev plan ability {ability.name} ({ability.get_prerequisite().name})")
            complete_ability_pins.append(ability_pin)

        self.report = ""
        self.action = Wander(self.game, self)
        self.bonus_action = None

        self.fake_action = Wander(None, self)
        self.fake_ability: Optional['Ability'] = None

        self.consumed_items: Set[int] = set()
        self.turn_conditions = []
        self.circuits: Iterable[Element] = []
        self.tentative_conditions = []
        self.temporary_abilities: List[int] = []

    def make_copy_for_simulation(self) -> 'Player':
        clone = Player(name=self.name+"_CLONE", progress_dict=self.progress_dict.copy(), dev_plan=self.dev_plan.copy(),
                       academics=self.academics, temperament=self.temperament, conditions=self.conditions.copy(),
                       items=self.items.copy(), money=self.credits,
                       relative_conditions={k: v[:] for k, v in self.relative_conditions.items()},
                       tattoo=self.tattoo,
                       game=self.game.clone())
        clone.consumed_items = self.consumed_items.copy()
        clone.turn_conditions = self.turn_conditions.copy()
        clone.tentative_conditions = self.tentative_conditions
        clone.temporary_abilities = self.temporary_abilities
        clone.circuits = self.circuits[:]
        return clone

    # Used for evaluating simulations
    def get_score(self) -> int:
        score = 0
        if self.is_dead():
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
        if not self.game.is_day() and self.has_ability("Awareness I"):
            self.report += os.linesep
            self.report += "You are Aware:" + os.linesep
            night_combat_report = DayReport().get_night_combat_report(self.name)
            if not night_combat_report:
                night_combat_report = "The night was peaceful."
            self.report += night_combat_report

        if (self.game.is_day() or self.has_ability("Panopticon")) and self.has_ability("Awareness II"):
            if len(DayReport().training) > 1 or (len(DayReport().training) == 1 and self not in DayReport().training):
                self.report += os.linesep
                self.report += "You are Aware:" + os.linesep
                for trainer in sorted(DayReport().training.keys(), key=lambda x: x.name):
                    if trainer != self:
                        self.report += f"{trainer.name} was training {DayReport().training[trainer]}." + os.linesep

        if self.has_ability("Panopticon"):
            self.report += os.linesep
            self.report += DayReport().get_action_report(pierce_illusions=True, ignore_player=self)
            self.report += os.linesep
            self.report += "INSERT PANOPTICON COMMENTARY HERE"
            self.report += os.linesep

        if self.has_ability("Attunement Detection"):
            self.report += os.linesep
            self.report += DayReport().get_attunement_report(self)

        if self.has_ability("Willpower Detection"):
            self.report += os.linesep
            self.report += DayReport().get_willpower_report(self)

        if self.has_ability("Market Connections I") or self.has_ability("Market Connections II"):
            self.report += os.linesep
            self.report += DayReport().get_money_report(full=self.has_ability("Market Connections II"))

        cleaned = self.report\
            .replace(COMBAT_PLACEHOLDER, DayReport().get_combat_report_for_player(self))\
            .replace(self.name+"'s", "your")\
            .replace(self.name, "you")\
            .replace("you was", "you were") \
            .replace("you is", "you are") \
            .replace("you healed themself", "you healed yourself") \
            .replace("you hurt themself", "you hurt yourself") \
            .replace("you tattooed themself", "you tattooed yourself") \
            .replace("your Poison Gas failed because they were Ambushed",
                     "your Poison Gas failed because you were Ambushed") \
            .replace("you animated their bunker",
                     "you animated your bunker") \
            .replace("your bunker collapsed around them",
                     "your bunker collapsed around you")

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

        return os.linesep.join(gather).replace("you while they", "you while you") \
            .replace("you (while they", "you (while you") \
            .replace("you were trying to heal themself", "you were trying to heal yourself") \
            .replace("you were trying to tattoo themself", "you were trying to tattoo yourself")

    def is_dead(self):
        return Condition.DEAD in self.conditions

    def _generic_action_check(self, bonus=False, day_only=False) -> NoReturn:
        if self.is_dead():
            raise Exception(f"Player {self.name} is DEAD and cannot act.")
        if bonus:
            if self.bonus_action:
                raise Exception(f"Player {self.name} is already taking a bonus.")
        else:
            if not isinstance(self.action, Wander):
                raise Exception(f"Player {self.name} is already taking an action.")
        if day_only:
            if not self.game.is_day():
                raise Exception(f"Player {self.name} is trying to take a day only action at night.")

    def plan_fake_ability(self, ability: Ability):
        self.fake_ability = ability

    def plan_fake_action(self, action):
        self.fake_action = action

    def plan_class(self):
        self._generic_action_check(day_only=True)
        self.action = Class(self.game, self)

    def plan_doctor(self):
        self._generic_action_check(day_only=True)
        self.action = Doctor(self.game, self)

    def plan_shop(self, *item_names):
        self._generic_action_check(day_only=True)
        item_names_to_amount = {}
        for item_name in item_names:
            if item_name not in item_names_to_amount:
                item_names_to_amount[item_name] = 0
            item_names_to_amount[item_name] += 1

        items = {get_item_by_name(item_name): amount for (item_name, amount) in item_names_to_amount.items()}

        for item in items:
            if item.cost < 0:
                raise Exception(f"Player {self.name} is trying to buy an item that is not for sale {item.name}.")

        if Shop.get_total_cost(items) > self.credits:
            raise Exception(f"Player {self.name} is trying to buy more than they can afford.")
        self.action = Shop(self.game, self, items)

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
        if len(targets) > 3:
            raise Exception(f"Player {self.name} is trying to attack too many enemies.")
        for target in targets:
            if target.name == self.name:
                raise Exception(f"Player {self.name} is trying to attack themselves.")
        filtered_targets = [target for target in targets if not target.is_dead()]
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
            raise Exception(f"Player {self.name} is trying to teach an ability they don't have ({ability_name}).")
        self.action = Teach(self.game, self, target, ability)

    def plan_learn(self, target: "Player"):
        self._generic_action_check()
        self.action = Learn(self.game, self, target)

    def plan_steal(self, target: "Player"):
        self._generic_action_check()
        self.action = Steal(self.game, self, target)

    def plan_spy(self, *targets: "Player"):
        self._generic_action_check(bonus=True)
        if self.game.is_day():
            raise Exception(f"Player {self.name} is trying to spy in broad daylight.")
        if not self.has_ability("Awareness II"):
            raise Exception(f"Player {self.name} is trying to spy but lacks the ability.")
        max_targets = 1
        if self.has_ability("Awareness III"):
            max_targets += 1
        if len(targets) > max_targets:
            raise Exception(f"Player {self.name} is trying to spy on too many targets.")
        for target in targets:
            if target == self:
                raise Exception(f"Player {self.name} is trying to spy on themself.")
            # It doesn't matter this overwrites. We just need at least one set to the Class
            self.bonus_action = Spy(self.game, self, target)

    def plan_blackmail(self, *targets: 'Player'):
        targets = set(targets)
        for target in targets:
            if not self.check_relative_condition(target, Condition.HOOK):
                raise Exception(f"Player {self.name} is trying to blackmail {target.name} when they don't have a hook.")
            Blackmail(self.game, self, target)

    def plan_consume_item(self, *item_names: 'str'):
        if self.consuming:
            raise Exception(f"Player {self.name} is trying to consume multiple times.")
        self.consuming = True
        for item_name in item_names:
            item = get_item_by_name(item_name)
            if item.pin in CONSUME_PREFER:
                if CONSUME_PREFER[item.pin] in self.items:
                    item = get_item(CONSUME_PREFER[item.pin])
            if item.pin not in self.items:
                raise Exception(f"Player {self.name} is trying to use an item they don't have ({item_name}).")
            if item.item_type != ItemType.CONSUMABLE:
                raise Exception(f"Player {self.name} is trying to use an item that isn't consumable ({item_name}).")
            ConsumeItem(self.game, self, item)  # Constructor adds it to the action queue

    def plan_trade(self, target: "Player", money: int = 0, item_names: Optional[List[str]] = None,
                   action_condition: Optional[Union[ACTION_CONDITION, Tuple['Player', Type['Action']]]] = None,
                   item_name_condition: Optional[Tuple["Player", int, List[str]]] = None):
        if action_condition:
            if len(action_condition) == 2:
                action_condition = (action_condition[0], action_condition[1], None)
        items: Optional[Dict['Item', int]] = None
        if item_names is not None:
            item_names_to_amount = {}
            for item_name in item_names:
                if item_name not in item_names_to_amount:
                    item_names_to_amount[item_name] = 0
                item_names_to_amount[item_name] += 1

            items = {get_item_by_name(item_name): amount for (item_name, amount) in item_names_to_amount.items()}

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

        Trade(self.game, self, target, items, money, action_condition, item_condition)

    def plan_face_mask(self, player: 'Player'):
        if self.masking:
            raise Exception(f"Player {self.name} is trying to mask multiple times.")
        self.masking = True
        if self.game.is_day():
            raise Exception(f"Player {self.name} is trying to use a Face Mask in broad daylight.")
        if FACE_MASK not in self.items:
            raise Exception(f"Player {self.name} is trying to use a Face Mask without owning one.")
        Disguise(self.game, self, player)

    def plan_attune(self, *elements: Element):
        if self.attuning:
            raise Exception(f"Player {self.name} is trying to attune multiple times.")
        if len(elements):
            self.attuning = True
            Attune(self.game, self, tuple(elements))

    def plan_craft_rune(self, ability_name: str, bonus=False):
        self._generic_action_check(bonus=bonus)
        items = {get_item_by_name(ability_name+" Rune"): 1}
        if bonus:
            self.bonus_action = Craft(self.game, self, items, is_bonus=True)
        else:
            self.action = Craft(self.game, self, items)

    def plan_tattoo(self, target: 'Player', ability_name: str):
        self._generic_action_check()
        rune = get_item_by_name(ability_name+" Rune")
        assert isinstance(rune, Rune)
        self.action = Tattoo(self.game, self, target, rune)

    def plan_get_tattoo(self, target: 'Player'):
        self.action = Canvas(self.game, self, target)

    def get_awareness(self):
        awareness = 0
        if self.has_ability("Awareness I"):
            awareness += 1
        if self.has_ability("Awareness II"):
            awareness += 1
        if self.has_ability("Awareness III"):
            awareness += 1
        return awareness

    def has_ability(self, ability_name: str, strict=False):
        ability = get_ability_by_name(ability_name)
        if not strict:
            if ability.pin in self.temporary_abilities:
                return True
        return ability.pin in self.progress_dict and self.progress_dict[ability.pin] >= ability.cost

    def get_abilities(self) -> List[Ability]:
        abilities = []
        for (ability_pin, progress) in self.progress_dict.items():
            ability = get_ability(ability_pin)
            if progress >= ability.cost:
                abilities.append(ability)
        return abilities

    def get_total_dev(self) -> int:
        total = 0
        for (ability_pin, progress) in self.progress_dict.items():
            total += progress
        return total

    def _check_attunement(self, attunement: Tuple[Element]) -> bool:
        total_circuits = (self.conditions + self.turn_conditions).count(Condition.CIRCUIT)
        max_anti = (self.conditions + self.turn_conditions).count(Condition.ANTI_CIRCUIT)
        max_fire = (self.conditions + self.turn_conditions).count(Condition.FIRE_CIRCUIT)
        max_water = (self.conditions + self.turn_conditions).count(Condition.WATER_CIRCUIT)
        max_earth = (self.conditions + self.turn_conditions).count(Condition.EARTH_CIRCUIT)
        max_air = (self.conditions + self.turn_conditions).count(Condition.AIR_CIRCUIT)
        max_light = (self.conditions + self.turn_conditions).count(Condition.LIGHT_CIRCUIT)

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

        return True

    # Returns if attunement was legal. Only sets if legal
    def set_attunement(self, attunement: Tuple[Element]) -> bool:
        if self._check_attunement(attunement):
            self.circuits = attunement[:]
            return True

        return False

    def get_one_swap_attunement(self) -> List[Tuple[Element]]:
        possibilities = {tuple(self.circuits)}
        if self.circuits:
            for i in range(len(list(self.circuits))):
                for element in Element:
                    possibility = tuple(self.circuits[:i]) + (element,) + tuple(self.circuits[i+1:])
                    possibilities.add(possibility)
        for element in Element:
            possibilities.add(tuple(self.circuits[:])+(element,))

        return [possibility for possibility in possibilities if self._check_attunement(possibility)]

    def get_possible_attunement(self) -> List[Tuple[Element]]:
        all_possibilities: List[Tuple[Element]] = []
        total_circuits = (self.conditions + self.turn_conditions).count(Condition.CIRCUIT)

        def legal_attunement(attunement: Tuple[Element]):
            return self._check_attunement(attunement)

        for i in range(total_circuits+1):
            possibilities = itertools.combinations_with_replacement([Element.ANTI, Element.FIRE, Element.WATER,
                                                                     Element.EARTH, Element.AIR, Element.LIGHT], i)
            all_possibilities.extend(filter(legal_attunement, possibilities))

        return all_possibilities

    def get_items(self, duplicates=True) -> List[Item]:
        if duplicates:
            return [get_item(pin) for pin in self.items]
        item_set = set(self.items)
        return [get_item(pin) for pin in item_set]

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
                if item.cost > cost:
                    best = item
                    cost = item.cost
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

    def get_skills(self) -> List[Skill]:
        skills = []
        for ability in self.get_abilities():
            skills += ability.get_skills(self.circuits)
        for item in self.get_items(duplicates=False):
            if item.item_type != ItemType.CONSUMABLE:
                skills += item.get_skills()
        for item in self.get_consumed_items():
            skills += item.get_skills()

        return skills

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

    def relative_condition_debug(self) -> List[str]:
        results = []
        for k, v in self.relative_conditions.items():
            for c in v:
                results.append(f"{k}_{c.name}")
        return results

    def total_progress(self) -> int:
        total = 0
        for progress in self.progress_dict.values():
            total += progress
        return total

    def gain_progress(self, progress: int) -> NoReturn:
        if Condition.DEAD in self.conditions:
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
        if ability.pin in self.dev_plan:
            self.dev_plan.remove(ability.pin)

    def copycat(self, target: 'Player', fake: 'bool' = False) -> NoReturn:
        available_abilities = [ability for ability in target.get_abilities()
                               if not self.has_ability(ability.name) and
                               (ability.get_prerequisite() is None or
                                self.has_ability(ability.get_prerequisite().name))]
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
            if info_scope == InfoScope.BROADCAST:
                DayReport().broadcast(message)
        return report_callable

    def wound(self, injury_modifiers: Optional[List[InjuryModifier]] = None,
              reporting_func: Optional[ReportCallable] = None) -> bool:
        if injury_modifiers is None:
            injury_modifiers = []
        if reporting_func is None:
            reporting_func = self._non_combat_report_callable()

        if LIZARD_TAIL in self.items:
            if InjuryModifier.NONLETHAL not in injury_modifiers or Condition.INJURED not in self.conditions:
                reporting_func(f"{self.name} used a Lizard Tail to avoid being wounded.", InfoScope.PUBLIC)
                self.items.remove(LIZARD_TAIL)
                reporting_func(f"Lizard Tail consumed ({self.items.count(LIZARD_TAIL)} remaining).", InfoScope.PRIVATE)
                return False

        if Condition.DEAD not in self.conditions:
            if Condition.INJURED in self.conditions:
                if InjuryModifier.NONLETHAL not in injury_modifiers:
                    reporting_func(f"{self.name} died.", InfoScope.BROADCAST)
                    self.conditions.append(Condition.DEAD)
                    return True
            else:
                if InjuryModifier.GRIEVOUS in injury_modifiers:
                    self.conditions.append(Condition.GRIEVOUS)
                    if InjuryModifier.PERMANENT in injury_modifiers:
                        self.conditions.append(Condition.CAUTERIZED)
                        reporting_func(f"{self.name} was permanently grievously injured.", InfoScope.PRIVATE)
                    else:
                        reporting_func(f"{self.name} was grievously injured.", InfoScope.PRIVATE)
                else:
                    if InjuryModifier.PERMANENT in injury_modifiers:
                        self.conditions.append(Condition.CAUTERIZED)
                        reporting_func(f"{self.name} was permanently injured.", InfoScope.PRIVATE)
                    else:
                        reporting_func(f"{self.name} was injured.", InfoScope.PRIVATE)
                self.conditions.append(Condition.INJURED)
                return True
        return False

    def petrify(self, reporting_func: Optional[ReportCallable] = None):
        if reporting_func is None:
            reporting_func = self._non_combat_report_callable()

        if Condition.PETRIFIED not in self.conditions:
            if SOFT in self.items:
                reporting_func(f"{self.name} used a Soft to avoid being petrified.", InfoScope.PUBLIC)
                self.items.remove(SOFT)
                reporting_func(f"Soft consumed ({self.items.count(LIZARD_TAIL)} remaining).", InfoScope.PRIVATE)
                return

            reporting_func(f"{self.name} was Petrified.", InfoScope.PUBLIC)
        # Reset Petrification Counter
        while self.conditions.count(Condition.PETRIFIED) < 2:
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

    def gain_credits(self, amount):
        self.credits += amount

    def lose_credits(self, amount):
        self.credits -= amount
        if self.credits < 0:
            self.credits = 0

    def gain_item(self, item: Item, amount=1):
        for i in range(amount):
            self.items.append(item.pin)
        self.report += f"{item.name} x{amount} gained ({self.items.count(item.pin)} total)" + os.linesep

    def lose_item(self, item: Item, amount=1):
        for i in range(amount):
            self.items.remove(item.pin)
        self.report += f"{item.name} x{amount} lost ({self.items.count(item.pin)} remaining)" + os.linesep

    def destroy_fragile_items(self):
        lost_items = {}
        for item in self.get_items(duplicates=True):
            if item.fragile:
                if item.pin not in lost_items:
                    lost_items[item.pin] = 0
                lost_items[item.pin] += 1
        for item_pin, amount in lost_items.items():
            self.lose_item(get_item(item_pin), amount)
