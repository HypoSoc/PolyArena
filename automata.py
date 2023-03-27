from typing import Optional, List, Dict, Union, Tuple, Type

from actions import Action, AutomataCraft, ACTION_CONDITION
from constants import Temperament, Condition, Element, InfoScope, InjuryModifier
from game import Game
from items import get_item_by_name
from player import Player, LIZARD_TAIL
from report import DayReport, ReportCallable
from skill import Skill, get_skill


class Automata(Player):
    def __init__(self, name: str, owner: 'Player',
                 conditions: List[Condition], items: List[int],
                 bounty: int,
                 relative_conditions: Dict[str, List[Condition]], tattoo: Optional[int],
                 game: Game):
        super().__init__(name, progress_dict={}, dev_plan=[], academics=0, temperament=Temperament.NONE,
                         conditions=conditions, items=items, money=0, willpower=0, bounty=bounty,
                         relative_conditions=relative_conditions, tattoo=tattoo,
                         game=game)
        self.owner = owner

        self.is_automata = True
        self.owner.automata_registry[self.name] = self

    def get_report(self):
        return ""

    def plan_class(self):
        raise Exception(f"Automata {self.name} cannot go to class.")

    def plan_doctor(self):
        raise Exception(f"Automata {self.name} cannot go to the doctor.")

    def plan_bounty(self, target: "Player", amount: int):
        raise Exception(f"Automata {self.name} cannot place a bounty.")

    def plan_train(self):
        raise Exception(f"Automata {self.name} cannot train.")

    def plan_teach(self, target: "Player", ability_name: str):
        raise Exception(f"Automata {self.name} cannot teach.")

    def plan_learn(self, target: "Player"):
        raise Exception(f"Automata {self.name} cannot learn.")

    def plan_steal(self, target: "Player"):
        raise Exception(f"Automata {self.name} cannot steal.")

    def plan_spy(self, *targets: "Player"):
        raise Exception(f"Automata {self.name} cannot spy.")

    def plan_blackmail(self, *targets: 'Player'):
        raise Exception(f"Automata {self.name} cannot blackmail.")

    def plan_trade(self, target: "Player", money: int = 0, item_names: Optional[List[str]] = None,
                   automata: Union[Optional[List[Union['Automata', str]]], 'Automata', str] = None,
                   action_condition: Optional[Union[ACTION_CONDITION, Tuple['Player', Type['Action']]]] = None,
                   item_name_condition: Optional[Tuple["Player", int, List[str]]] = None):
        if money:
            raise Exception(f"Automata {self.name} cannot trade money.")
        if automata:
            raise Exception(f"Automata {self.name} cannot trade automata.")

        super().plan_trade(target=target, money=money, item_names=item_names,
                           action_condition=action_condition,
                           item_name_condition=item_name_condition)

    def plan_attune(self, *elements: Element):
        raise Exception(f"Automata {self.name} cannot attune.")

    def plan_hydro(self, ability_name: str, will: Union[Optional[List[int]], int] = None, contingency: bool = False,
                   targets: Union[Optional[List['Player']], 'Player'] = None):
        raise Exception(f"Automata {self.name} cannot use hydromancy.")

    def plan_illusion(self, target: 'Player', action: 'Action', ability: Optional[str]):
        raise Exception(f"Automata {self.name} cannot use hydromancy.")

    def plan_craft(self, *item_names, automata_name: Union[Optional[List[str]], str] = None):
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

        items = {get_item_by_name(item_name): amount for (item_name, amount) in item_names_to_amount.items()}

        self.action = AutomataCraft(self.game, self, items, automata_names=automata_name)

    def plan_craft_rune(self, ability_name: str, bonus=False):
        self._generic_action_check(bonus=bonus)
        items = {get_item_by_name(ability_name+" Rune"): 1}
        if bonus:
            raise Exception("Automata cannot take bonus crafting actions.")
        self.action = AutomataCraft(self.game, self, items)

    def get_skills(self) -> List[Skill]:
        automata_skills = [get_skill(22), get_skill(2), get_skill(2)]  # Gas Immune and 0/2 Stat baseline
        automata_skills.extend(super(Automata, self).get_skills())
        return automata_skills

    def gain_progress(self, progress: int):
        return

    def copycat(self, target: 'Player', fake: 'bool' = False):
        return

    def die(self, message, reporting_func: Optional[ReportCallable] = None):
        if not reporting_func:
            reporting_func = self._non_combat_report_callable()
        self.conditions.append(Condition.DEAD)
        reporting_func(message, InfoScope.BROADCAST)
        DayReport().add_death(self)

    def wound(self, injury_modifiers: Optional[List[InjuryModifier]] = None,
              reporting_func: Optional[ReportCallable] = None) -> bool:
        if reporting_func is None:
            reporting_func = self._non_combat_report_callable()

        if LIZARD_TAIL in self.items:
            reporting_func(f"{self.name} used a Lizard Tail to avoid being wounded.", InfoScope.PUBLIC)
            self.items.remove(LIZARD_TAIL)
            reporting_func(f"Lizard Tail consumed ({self.items.count(LIZARD_TAIL)} remaining).", InfoScope.PRIVATE)
            return False

        if Condition.DEAD not in self.conditions:
            self.die(f"{self.name} was destroyed.", reporting_func)
            return True
        return False

    def heal(self) -> bool:
        return False

    def get_credits(self):
        return self.owner.credits

    def gain_credits(self, amount):
        self.owner.gain_credits(amount)

    def lose_credits(self, amount):
        self.owner.lose_credits(amount)