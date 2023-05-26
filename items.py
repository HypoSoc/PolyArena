from __future__ import annotations

import glob
from typing import List, Dict

from yaml import safe_load

from ability import get_ability, get_ability_by_name
from constants import ItemType
from skill import Skill, get_skill


__item_dict = {}

RUNE_INDEX = 10000


class Item:
    def __init__(self, pin: int, name: str, alt_name: str, cost: int, skill_pins: List[int],
                 item_type: ItemType, loot: bool, fragile: bool, stacking: bool):
        self.pin = pin
        self.name = name
        self.alt_name = alt_name
        self.cost = cost
        self.skill_pins = skill_pins
        self.item_type = item_type
        self.loot = loot
        self.fragile = fragile  # Destroy if would be stolen
        self.stacking = stacking
        self.destruction_message = "destroyed"
        if self.item_type in [ItemType.CONSUMABLE, ItemType.REACTIVE]:
            self.destruction_message = "consumed"

    def get_skills(self, choice=-1) -> List[Skill]:
        try:
            skills = []
            for skill_pin in self.skill_pins:
                skill = get_skill(skill_pin)
                skill.source = self
                skills.append(skill)
            return skills
        except Exception as e:
            raise Exception(f"Failed to parse skills for Item {self.name} ({self.pin})") from e

    def __str__(self):
        cost = self.cost
        if cost < 0:
            cost = "Not for Sale"
        return f"{self.name} ({cost})"


class Rune(Item):
    def __init__(self, pin: int):
        assert pin > RUNE_INDEX
        ability = get_ability(pin - RUNE_INDEX)
        name = f"{ability.name} Rune"
        super().__init__(pin, name=name, alt_name=name, cost=-2, skill_pins=[], item_type=ItemType.CONSUMABLE,
                         loot=True, fragile=False, stacking=False)

    def get_skills(self, choice=-1) -> List[Skill]:
        return get_ability(self.pin - RUNE_INDEX).get_skills_for_rune(choice=choice)

    def is_disruptive(self) -> bool:
        if get_ability(self.pin - RUNE_INDEX).geo_qualified_skills:
            return True
        return False

    # Rune Crafting 1
    def is_simple_rune(self):
        ability = get_ability(self.pin - RUNE_INDEX)
        while ability.get_prerequisite():
            ability = ability.get_prerequisite()
        return ability.pin == get_ability_by_name("Circuit I").pin

    def get_ability_pin(self) -> int:
        return self.pin - RUNE_INDEX

    def get_ability_name(self) -> str:
        return get_ability(self.pin - RUNE_INDEX).name


def get_item(pin: int) -> Item:
    try:
        if pin > RUNE_INDEX:
            return Rune(pin)
        return __item_dict[pin]
    except (Exception, KeyError):
        raise Exception(f"Item {pin} does not exist.")


def get_item_by_name(name: str) -> Item:
    if name.lower().endswith(" rune"):
        return Rune(get_ability_by_name(name.lower()[:-5]).pin+RUNE_INDEX)
    for item in __item_dict.values():
        if item.name.lower() == name.lower() or item.alt_name.lower() == name.lower():
            return item
    raise Exception(f"Item {name} not found")


def __parse_item(pin: int, dictionary: Dict) -> Item:
    for key in dictionary.keys():
        assert key in ['name', 'alt_name', 'cost',
                       'skills', 'type', 'loot', 'fragile', 'stacking'], f"Item {pin}: illegal key {key}"
    return Item(pin=pin, name=dictionary['name'], alt_name=dictionary.get('alt_name', dictionary['name']),
                cost=dictionary['cost'],
                skill_pins=dictionary['skills'],
                item_type=ItemType[dictionary.get('type', "PERMANENT")],
                loot=dictionary.get('loot', True),
                fragile=dictionary.get('fragile', False),
                stacking=dictionary.get('stacking', False))


if not __item_dict:
    file_names = ['data/items.yaml']
    file_names.extend(
        glob.glob("data/aeromancy_items/*.yaml")
    )
    for file_name in file_names:
        with open(file_name) as file:
            item_list = safe_load(file)
            for (k, v) in item_list.items():
                if k in __item_dict:
                    raise Exception(f"ID collision in {file_name} {k}")
                __item_dict[k] = __parse_item(k, v)
