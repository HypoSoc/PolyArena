import glob
from typing import TYPE_CHECKING, Dict, Optional, Any, List

from yaml import safe_load

from constants import Condition, Effect, InfoScope, Trigger

__skill_dict = {}

if TYPE_CHECKING:
    from player import Player


class Skill:
    def __init__(self, pin: int, text: str, effect: Effect, value: Any, priority: int, info: InfoScope,
                 trigger: Trigger, self_override: bool = False, value_b: Optional[Any] = None,
                 works_when_petrified: bool = False, info_once_override: bool = False,
                 works_through_counterint: bool = False, consume_charge: bool = False,
                 self_has_condition: Optional[Condition] = None, self_not_condition: Optional[Condition] = None,
                 target_has_condition: Optional[Condition] = None, target_not_condition: Optional[Condition] = None,
                 condition_list: Optional[List[Condition]] = None):
        self.pin = pin
        self.text = text
        self.effect = effect
        self.value = value
        self.priority = priority
        self.info = info
        self.trigger = trigger
        self.self_override = self_override
        self.value_b = value_b
        self.works_when_petrified = works_when_petrified
        self.info_once_override = info_once_override
        self.works_through_counterint = works_through_counterint
        self.consume_charge = consume_charge
        self.self_has_condition = self_has_condition
        self.self_not_condition = self_not_condition
        self.target_has_condition = target_has_condition
        self.target_not_condition = target_not_condition
        self.condition_list = condition_list

        self.source = None  # Helps to debug
        self.fragile: Optional[Condition] = None
        self.player_of_origin: Optional['Player'] = None
        self.read_only = True

        self.targets = []  # Used for Trigger.TARGET skills

    def copy(self) -> 'Skill':
        copied = Skill(pin=self.pin, text=self.text, effect=self.effect, value=self.value, priority=self.priority,
                       info=self.info, trigger=self.trigger, self_override=self.self_override, value_b=self.value_b,
                       works_when_petrified=self.works_when_petrified, info_once_override=self.info_once_override,
                       works_through_counterint=self.works_through_counterint, consume_charge=self.consume_charge,
                       self_has_condition=self.self_has_condition, self_not_condition=self.self_not_condition,
                       target_has_condition=self.target_has_condition, target_not_condition=self.target_not_condition,
                       condition_list=self.condition_list)
        copied.source = self.source
        copied.fragile = self.fragile
        copied.player_of_origin = self.player_of_origin
        copied.read_only = False
        return copied

    def set_fragile(self, fragile: Condition):
        assert not self.read_only, f"Trying to modify a read only skill: {self.pin}"
        self.fragile = fragile


def get_skill(pin: int) -> Skill:
    try:
        return __skill_dict[pin].copy()
    except KeyError:
        raise Exception(f"Skill {pin} does not exist.")


def __parse_skill(pin: int, dictionary: Dict) -> Skill:
    sc = None
    if 'self_has_condition' in dictionary:
        sc = Condition[dictionary['self_has_condition']]
    snc = None
    if 'self_not_condition' in dictionary:
        snc = Condition[dictionary['self_not_condition']]
    tc = None
    if 'target_has_condition' in dictionary:
        tc = Condition[dictionary['target_has_condition']]
    tnc = None
    if 'target_not_condition' in dictionary:
        tnc = Condition[dictionary['target_not_condition']]

    clist = None
    if 'condition_list' in dictionary:
        clist = list(map(lambda c: Condition[c], dictionary['condition_list']))

    for key in dictionary.keys():
        assert key in ['text', 'effect', 'value', 'value_b', 'priority', 'info', 'trigger', 'self_override',
                       'works_when_petrified',
                       'self_has_condition', 'self_not_condition',
                       'target_has_condition', 'target_not_condition', 'info_once', 'condition_list',
                       'works_through_counter_int', 'consume_charge'],\
            f"Skill {pin}: illegal key {key}"
    return Skill(pin=pin, text=dictionary['text'], effect=Effect[dictionary['effect']],
                 value=dictionary.get('value', 0), priority=dictionary.get('priority', 0),
                 info=InfoScope[dictionary.get('info', "HIDDEN")],
                 trigger=Trigger[dictionary.get('trigger', "SELF")],
                 self_override=dictionary.get('self_override', False),
                 value_b=dictionary.get('value_b'),
                 works_when_petrified=dictionary.get('works_when_petrified'),
                 info_once_override=dictionary.get('info_once', False),
                 works_through_counterint=dictionary.get('works_through_counter_int', False),
                 self_has_condition=sc,
                 self_not_condition=snc,
                 target_has_condition=tc,
                 target_not_condition=tnc,
                 condition_list=clist,
                 consume_charge=dictionary.get('consume_charge', False))


if not __skill_dict:
    file_names = ["data/skills.yaml"]
    file_names.extend(
        glob.glob("data/aeromancy_skills/*.yaml")
    )
    file_names.extend(
        glob.glob("data/madness_skills/*.yaml")
    )
    for file_name in file_names:
        with open(file_name) as file:
            skill_list = safe_load(file)
            for (k, v) in skill_list.items():
                if k in __skill_dict:
                    raise Exception(
                        f"ID collision in skills.yaml {k} {v} {__skill_dict[k].text}")
                __skill_dict[k] = __parse_skill(k, v)
