from __future__ import annotations

import glob
import itertools
import os
from typing import List, Optional, Tuple, Iterable, Dict

from yaml import safe_load

from constants import Element, Condition, Trigger, Effect, NONCOMBAT_TRIGGERS, InfoScope
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
                    if skill.trigger not in NONCOMBAT_TRIGGERS:
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

            # To prevent multi triggers of progress, we combine them into a single skill for the each case
            skills.append(skill)
            if skill.effect == Effect.PROGRESS:
                skill.value *= times
                break
        return skills


class AeroQualifiedSkill:
    def __init__(self, pin: int, fragile: Optional[Condition] = None, option: int = -1):
        self.pin = pin
        self.fragile = fragile
        self.option = option

    def get_skills(self, option: int, for_rune=False) -> List[Skill]:
        if -1 < self.option != option:
            return []  # Option not chosen

        skill = get_skill(self.pin).copy()
        if not for_rune:
            if self.fragile:
                skill.set_fragile(self.fragile)
                if skill.trigger not in NONCOMBAT_TRIGGERS:
                    if skill.priority < 20:  # Fragile Skills have to happen after antimagic
                        skill.priority = 20

        return [skill]


class Ability:
    def __init__(self, pin: int, name: str, cost: int, skill_pins: List[int],
                 geo_qualified_skills: List[GeoQualifiedSkill],
                 hydro_qualified_skills: List[HydroQualifiedSkill],
                 aero_qualified_skills: List[AeroQualifiedSkill],
                 max_will: int, contingency_forbidden: bool, linked: bool,
                 concept: Optional[str],
                 max_targets: int,
                 must_choose: int,
                 explanation: str,
                 prerequisite_pin: Optional[int] = None):
        self.pin = pin
        self.name = name
        self.cost = cost
        self.skill_pins = skill_pins
        self.geo_qualified_skills = geo_qualified_skills
        self.hydro_qualified_skills = hydro_qualified_skills
        self.aero_qualified_skills = aero_qualified_skills
        self.max_will = max_will
        self.contingency_forbidden = contingency_forbidden
        self.linked = linked
        self.concept = concept
        self.max_targets = max_targets
        self.must_choose = must_choose  # must_choose: number of options
        self.explanation = explanation   # Adds an on acquisition skill to explain what a concept level does
        self.prerequisite_pin = prerequisite_pin

    def get_prerequisite(self) -> Optional[Ability]:
        if self.prerequisite_pin:
            return get_ability(self.prerequisite_pin)
        return None

    def _get_aero_skills(self, choice, for_rune=False) -> List[Skill]:
        if self.must_choose:
            assert choice >= 0, f"No choice made for {self.name}."
            assert choice < self.must_choose, f"Illegal choice made for {self.name}."
        return [skill for qualified in self.aero_qualified_skills
                for skill in qualified.get_skills(option=choice, for_rune=for_rune)]

    def get_skills(self, circuits: Iterable[Element], will: List[int], choice: int = -1) -> List[Skill]:
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
            skills.extend(self._get_aero_skills(choice))
            skills.extend(self._get_aeromancy_explanation_skill())
            return skills
        except Exception as e:
            raise Exception(f"Failed to parse skills for Ability {self.name} ({self.pin})") from e

    def get_skills_for_rune(self, choice=-1) -> List[Skill]:
        try:
            skills = list(map(get_skill, self.skill_pins))
            skills.extend([skill for qualified in self.geo_qualified_skills
                           for skill in qualified.get_skills(FULL_ELEMENTS, for_rune=True)])
            skills.extend([skill for qualified in self.hydro_qualified_skills
                           for skill in qualified.get_skills(qualified.cost, for_rune=True)])
            skills.extend(self._get_aero_skills(choice, for_rune=True))
            return skills
        except Exception as e:
            raise Exception(f"Failed to parse skills for Ability {self.name} ({self.pin})") from e

    def get_skills_for_hydro_contingency(self, will: List[int]) -> List[Skill]:
        return [skill for i in range(len(self.hydro_qualified_skills))
                for skill in self.hydro_qualified_skills[i].get_skills(will[i]) if skill.trigger in NONCOMBAT_TRIGGERS]

    def is_copyable(self) -> bool:
        # Aeromancy is not copyable
        if self.pin == 307:
            return True
        if 300 < self.pin < 399:
            return False
        return self.pin < 700

    def _get_index(self) -> Tuple[int, int, int]:
        pin = self.pin
        if pin > 700:  # Aeromancy Concept
            pin = 300 + self.pin % 100
        if self.prerequisite_pin is None:
            return 0, pin, self.pin
        return self.get_prerequisite()._get_index()[0] + 1, pin, self.pin

    def _get_aeromancy_explanation_skill(self) -> List[Skill]:
        if self.explanation:
            return [Skill(pin=-999, text=f"{self.name} ({self.cost}){os.linesep}{self.explanation}{os.linesep}",
                          effect=Effect.INFO_ONCE, value=None, priority=0,
                          info=InfoScope.PERSONAL, trigger=Trigger.ACQUISITION)]
        return []

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
    aero_qualified_skills = []
    for entry_pin, entry_value in dictionary.get('geo', {}).items():
        for key in entry_value.keys():
            assert key in ['circuits', 'each', 'fragile'], f"Ability {pin}, illegal key geo {key}"

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
        for key in entry_value.keys():
            assert key in ['cost', 'each', 'fragile'], f"Ability {pin}, illegal key hydro {key}"

        fragile = None
        if entry_value.get('fragile', None):
            fragile = Condition.HYDRO_LOCKED
        hydro_qualified_skills.append(HydroQualifiedSkill(pin=entry_pin, cost=entry_value['cost'],
                                                          each=entry_value.get('each', False), fragile=fragile))

    for entry_pin, entry_value in dictionary.get('aero', {}).items():
        for key in entry_value.keys():
            assert key in ['fragile', 'option'], f"Ability {pin}, illegal key aero {key}"

        fragile = None
        if entry_value.get('fragile', None):
            fragile = Condition.AERO_LOCKED
        aero_qualified_skills.append(AeroQualifiedSkill(pin=entry_pin, fragile=fragile,
                                                        option=entry_value.get('option', -1)))

    skills = []
    if 'skills' in dictionary:
        skills = dictionary['skills']

    for key in dictionary.keys():
        assert key in ['name', 'cost', 'skills', 'geo', 'hydro', 'aero', 'max_will', 'not_contingency', 'linked',
                       'concept', 'max_targets', 'must_choose', 'explanation', 'prerequisite'], \
            f"Ability {pin}, illegal key {key}"
    return Ability(pin=pin, name=dictionary['name'], cost=dictionary['cost'],
                   skill_pins=skills,
                   geo_qualified_skills=geo_qualified_skills,
                   hydro_qualified_skills=hydro_qualified_skills,
                   aero_qualified_skills=aero_qualified_skills,
                   max_will=dictionary.get('max_will', 1000000),
                   contingency_forbidden=dictionary.get('not_contingency', False),
                   linked=dictionary.get('linked', False),
                   concept=dictionary.get('concept'),
                   max_targets=dictionary.get('max_targets', 1),
                   must_choose=dictionary.get('must_choose', 0),
                   explanation=dictionary.get('explanation', ""),
                   prerequisite_pin=dictionary.get('prerequisite'))


if not __ability_dict:
    file_names = ['data/geo_abilities.yaml', 'data/hydro_abilities.yaml',
                  'data/aero_abilities.yaml',
                  'data/body_abilities.yaml', 'data/mind_abilities.yaml']
    file_names.extend(
        glob.glob("data/aeromancy_abilities/*.yaml")
    )
    for file_name in file_names:
        with open(file_name) as file:
            ability_list = safe_load(file)
            if ability_list:
                for (k, v) in ability_list.items():
                    if k in __ability_dict:
                        raise Exception(f"ID collision in {file_name} {k}")
                    __ability_dict[k] = __parse_ability(k, v)
