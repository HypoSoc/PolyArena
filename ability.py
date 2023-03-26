from __future__ import annotations

import itertools
import os
from typing import List, Optional, Tuple, Iterable, Dict

from yaml import safe_load

from constants import Element, Condition, Trigger, Effect, NONCOMBAT_TRIGGERS
from skill import Skill, get_skill


__ability_dict = {}
FULL_ELEMENTS = [element for element in Element] * 3


class GeoQualifiedSkill:
    def __init__(self, pin: int, circuits: List[List[Element]], each: bool = False,
                 fragile: Optional[Condition] = None):
        self.pin = pin
        self.circuits = circuits
        self.each = each
        self.fragile = fragile

    def _count_times(self, attuned: Iterable[Element]) -> int:
        if self.each:
            assert len(self.circuits) == 1, f"Qualified Skill {self.pin} with 'Each' can't have multiple options."
            assert len(self.circuits[0]) == 1, f"Qualified Skill {self.pin} with 'Each' can't have multiple circuits " \
                                               f"required. "
            return list(attuned).count(self.circuits[0][0])
        else:
            for legal_arrangement in self.circuits:
                check_attuned = list(attuned)
                legal = True
                for element in legal_arrangement:
                    if element in check_attuned:
                        check_attuned.remove(element)
                    else:
                        legal = False
                        break
                if legal:
                    return 1
            return 0

    def get_skills(self, attuned: Iterable[Element], for_rune=False) -> List[Skill]:
        skills = []
        times = self._count_times(attuned)
        for i in range(times):
            skill = get_skill(self.pin).copy()
            if not for_rune:
                if self.fragile:
                    skill.set_fragile(self.fragile)
                    if skill.priority < 20:  # Fragile Skills have to happen after antimagic
                        skill.priority = 20
                if skill.trigger == Trigger.NONCOMBAT:
                    skill.trigger = Trigger.NONCOMBAT_POST_ATTUNE
                    if skill.effect == Effect.CONDITION:
                        skill.effect = Effect.TENTATIVE_CONDITION
            # To prevent multi triggers of progress, we combine them into a single skill for the each case
            skills.append(skill)
            if skill.effect == Effect.PROGRESS:
                skill.value *= times
                break
        return skills


class HydroQualifiedSkill:
    def __init__(self, pin: int, cost: int, each: bool = False,
                 fragile: Optional[Condition] = None):
        self.pin = pin
        self.cost = cost  # For repeatable skills, this is the maximum that can be spent, otherwise it is the cost
        self.each = each
        self.fragile = fragile

    def get_skills(self, will: int, for_rune=False) -> List[Skill]:
        skills = []
        times = will >= self.cost
        if self.each:
            times = min(will, self.cost)
        for i in range(times):
            skill = get_skill(self.pin).copy()
            if not for_rune:
                if self.fragile:
                    skill.set_fragile(self.fragile)
                    if skill.trigger not in NONCOMBAT_TRIGGERS:
                        if skill.priority < 20:  # Fragile Skills have to happen after antimagic
                            skill.priority = 20
                    if skill.effect == Effect.CONDITION:
                        skill.effect = Effect.TENTATIVE_CONDITION
                        if skill.priority < 20:  # Fragile Skills have to happen after antimagic
                            skill.priority = 20

            # To prevent multi triggers of progress, we combine them into a single skill for the each case
            skills.append(skill)
            if skill.effect == Effect.PROGRESS:
                skill.value *= times
                break
        return skills


class Ability:
    def __init__(self, pin: int, name: str, cost: int, skill_pins: List[int],
                 geo_qualified_skills: List[GeoQualifiedSkill],
                 hydro_qualified_skills: List[HydroQualifiedSkill],
                 max_will: int, contingency_forbidden: bool, linked: bool,
                 prerequisite_pin: Optional[int] = None):
        self.pin = pin
        self.name = name
        self.cost = cost
        self.skill_pins = skill_pins
        self.geo_qualified_skills = geo_qualified_skills
        self.hydro_qualified_skills = hydro_qualified_skills
        self.max_will = max_will
        self.contingency_forbidden = contingency_forbidden
        self.linked = linked
        self.prerequisite_pin = prerequisite_pin

    def get_prerequisite(self) -> Optional[Ability]:
        if self.prerequisite_pin:
            return get_ability(self.prerequisite_pin)
        return None

    def get_skills(self, circuits: Iterable[Element], will: List[int]) -> List[Skill]:
        while len(will) < len(self.hydro_qualified_skills):
            if self.linked and will:
                will.append(will[0])  # Multiple skills for the same willpower
            else:
                will.append(0)
        try:
            skills = list(map(get_skill, self.skill_pins))
            skills.extend([skill for qualified in self.geo_qualified_skills
                           for skill in qualified.get_skills(circuits)])
            skills.extend([skill for i in range(len(self.hydro_qualified_skills))
                           for skill in self.hydro_qualified_skills[i].get_skills(will[i])])
            return skills
        except Exception as e:
            raise Exception(f"Failed to parse skills for Ability {self.name} ({self.pin})") from e

    def get_skills_for_rune(self) -> List[Skill]:
        try:
            skills = list(map(get_skill, self.skill_pins))
            skills.extend([skill for qualified in self.geo_qualified_skills
                           for skill in qualified.get_skills(FULL_ELEMENTS, for_rune=True)])
            skills.extend([skill for qualified in self.hydro_qualified_skills
                           for skill in qualified.get_skills(qualified.cost, for_rune=True)])
            return skills
        except Exception as e:
            raise Exception(f"Failed to parse skills for Ability {self.name} ({self.pin})") from e

    def get_skills_for_hydro_contingency(self, will: List[int]) -> List[Skill]:
        return [skill for i in range(len(self.hydro_qualified_skills))
                for skill in self.hydro_qualified_skills[i].get_skills(will[i]) if skill.trigger in NONCOMBAT_TRIGGERS]

    def is_copyable(self) -> bool:
        # Aeromancy is not copyable
        # TODO Legacy Magic is not copyable, but Reality Warp is
        return self.pin < 600

    def _get_index(self) -> Tuple[int, int, int]:
        pin = self.pin
        if pin > 600:  # Aeromancy Concept
            pin = 300 + self.pin % 100
        if self.prerequisite_pin is None:
            return 0, pin, self.pin
        return self.get_prerequisite()._get_index()[0] + 1, pin, self.pin

    def __str__(self):
        val = f"{self.name} ({self.cost}):{os.linesep}"
        for skill in self.get_skills(FULL_ELEMENTS, [qualified.cost for qualified in self.hydro_qualified_skills]):
            val += skill.text
            if skill.fragile:
                val += " (Fragile)"
            val += os.linesep
        return val

    def __eq__(self, other: 'Ability'):
        return self._get_index() == other._get_index()

    def __lt__(self, other: 'Ability'):
        return self._get_index() < other._get_index()


def get_ability(pin: int) -> Ability:
    try:
        return __ability_dict[pin]
    except KeyError:
        raise Exception(f"Ability {pin} does not exist.")


def get_ability_by_name(name: str) -> Ability:
    for ability in __ability_dict.values():
        if ability.name.lower() == name.lower():
            return ability
    raise Exception(f"Ability {name} not found")


def __parse_ability(pin: int, dictionary: Dict) -> Ability:
    geo_qualified_skills = []
    hydro_qualified_skills = []
    for entry_pin, entry_value in dictionary.get('geo', {}).items():
        circuits = []
        element_options: List[List[Element]] = []
        for element_string in entry_value['circuits']:
            element_options.append([Element[component] for component in element_string.split("/")])
        for option in itertools.product(*element_options):
            circuits.append(list(option))
        fragile = None
        if entry_value.get('fragile', None):
            fragile = Condition.GEO_LOCKED
        geo_qualified_skills.append(GeoQualifiedSkill(pin=entry_pin, circuits=circuits,
                                                      each=entry_value.get('each', False), fragile=fragile))

    for entry_pin, entry_value in dictionary.get('hydro', {}).items():
        fragile = None
        if entry_value.get('fragile', None):
            fragile = Condition.HYDRO_LOCKED
        hydro_qualified_skills.append(HydroQualifiedSkill(pin=entry_pin, cost=entry_value['cost'],
                                                          each=entry_value.get('each', False), fragile=fragile))

    skills = []
    if 'skills' in dictionary:
        skills = dictionary['skills']
    return Ability(pin=pin, name=dictionary['name'], cost=dictionary['cost'],
                   skill_pins=skills,
                   geo_qualified_skills=geo_qualified_skills,
                   hydro_qualified_skills=hydro_qualified_skills,
                   max_will=dictionary.get('max_will', 1000000),
                   contingency_forbidden=dictionary.get('not_contingency', False),
                   linked=dictionary.get('linked', False),
                   prerequisite_pin=dictionary.get('prerequisite'))


if not __ability_dict:
    for file_name in ['data/geo_abilities.yaml', 'data/hydro_abilities.yaml',
                      'data/body_abilities.yaml', 'data/mind_abilities.yaml']:
        with open(file_name) as file:
            ability_list = safe_load(file)
            for (k, v) in ability_list.items():
                if k in __ability_dict:
                    raise Exception(f"ID collision in {file_name} {k}")
                __ability_dict[k] = __parse_ability(k, v)
