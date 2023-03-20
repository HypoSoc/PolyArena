from ability import get_ability_by_name
from actions import *
import combat
from constants import Temperament, Condition
from game import Game
from items import get_item_by_name
from player import Player
from report import DayReport

GAME = Game(night=False)


def create_player(name: str, abilities=None, items=None, injured: bool = False,
                  dev_goals=None, temperament=Temperament.ALTRUISTIC,
                  tattoo=None) -> Player:
    if dev_goals is None:
        dev_goals = []
    if items is None:
        items = []
    if abilities is None:
        abilities = []
    devs = {}
    for ability_name in abilities:
        ability = get_ability_by_name(ability_name)
        devs[ability.pin] = ability.cost
        prereq = ability.get_prerequisite()
        while prereq and prereq.pin not in devs:
            devs[prereq.pin] = prereq.cost
            prereq = prereq.get_prerequisite()

    item_pins = []
    for item_names in items:
        item = get_item_by_name(item_names)
        item_pins.append(item.pin)

    dev_list = []
    for dev_name in dev_goals:
        dev_list.append(get_ability_by_name(dev_name).pin)

    conditions = []
    if injured:
        conditions.append(Condition.INJURED)

    if tattoo:
        tattoo = get_item_by_name(tattoo+" Rune").pin

    player = Player(name, devs, dev_list, academics=0, conditions=conditions, temperament=temperament,
                    items=item_pins, money=10, relative_conditions={}, tattoo=tattoo,
                    game=GAME)

    def patient():
        Action.progress(player, 20)

    if temperament == Temperament.PATIENT:
        GAME.add_event(5, False, patient)

    return player


if __name__ == '__main__':
    combat.DEBUG = False  # Shows stats, items, and conditions in reports as public information
    a = create_player("Alpha", ["Water III", "Circuit V", "Light I", "Antimagic (Geo)",
                                "Runic Tattoos", "Awareness I", "Magical Healing (Geo)"],
                      ["Venom", "Face Mask", "Oxygen Mask", "Poison Gas", "Sword", "Fire II Rune"],
                      injured=False)
    b = create_player("Beta", ["Martial Arts II", "Circuit III",
                               "Earth III", "Petrification I"],
                      ["1/2 Medkit", "Poison Gas", "Bunker Shields", "Bunker Munitions", "Venom",
                       "Healing Tank", "Booby Trap"],
                      dev_goals=["Martial Arts III"])
    c = create_player("Charlie", ["Theft", "Armed Combat II", "Martial Arts III", "Water II", "Earth III",
                                  "Circuit III"],
                      ["Venom", "Poison Gas", "Oxygen Mask", "Face Mask", "Synthetic Weave", "Earth III Rune"],
                      dev_goals=[])
    d = create_player("Delta", ["Attunement Detection", "Willpower Detection"], temperament=Temperament.PATIENT,
                      items=["Shrooms", "Medkit"],
                      dev_goals=["Martial Arts I", "Martial Arts II", "Armed Combat I", "Armed Combat II"])
    GAME.advance()

    a.plan_attack(b)
    a.plan_attune(Element.LIGHT, Element.WATER)
    b.plan_bunker(bonus=True)
    b.plan_attune(Element.EARTH, Element.EARTH, Element.EARTH)
    b.plan_attack(a)
    c.plan_steal(b)
    d.plan_class()

    Action.run_turn(GAME)

    for p in [a, b, c, d]:
        print(f"{p.name} Report")
        print(p.get_report())
        if p.tattoo:
            print(get_item(p.tattoo))
        print()

    print(DayReport().generate_report(GAME))


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
