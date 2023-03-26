from actions import *
import combat
from constants import Temperament, Condition
from game import Game
from items import get_item_by_name
from player import Player
from report import DayReport

GAME = Game(night=False)


def create_player(name: str, abilities=None, items=None, injured: bool = False, hiding: bool = False,
                  dev_goals=None, temperament=Temperament.HOT_BLOODED,
                  tattoo=None) -> Player:
    if dev_goals is None:
        dev_goals = []
    if items is None:
        items = []
    if abilities is None:
        abilities = []
    devs = {}

    willpower = 0

    for ability_name in abilities:
        ability = get_ability_by_name(ability_name)
        devs[ability.pin] = ability.cost
        for skill in ability.get_skills([], []):
            if skill.effect == Effect.MAX_WILLPOWER:
                willpower += skill.value
        prereq = ability.get_prerequisite()
        while prereq and prereq.pin not in devs:
            devs[prereq.pin] = prereq.cost
            for skill in prereq.get_skills([], []):
                if skill.effect == Effect.MAX_WILLPOWER:
                    willpower += skill.value
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
    if hiding:
        conditions.append(Condition.HIDING)

    if tattoo:
        tattoo = get_item_by_name(tattoo+" Rune").pin

    player = Player(name, devs, dev_list, academics=0, conditions=conditions, temperament=temperament,
                    items=item_pins, money=3, willpower=willpower, relative_conditions={}, tattoo=tattoo,
                    game=GAME)

    def patient():
        Action.progress(player, 20)

    if temperament == Temperament.PATIENT:
        GAME.add_event(5, False, patient)

    return player


if __name__ == '__main__':
    combat.DEBUG = True  # Shows stats, items, and conditions in reports as public information
    a = create_player("Alpha", ["Willpower V", "Mental Reinforcement III"],
                      ["Healing Tank", "Oxygen Mask", "Booby Trap", "Fire II Rune", "Leather Armor", "Bokken"],
                      hiding=False)
    b = create_player("Beta", ["Circuit V", "Earth III", "Awareness I", "Willpower Draining", "Light II"],
                      ["1/2 Medkit", "Poison Gas", "Bunker Shields", "Bunker Munitions", "Venom",
                       "Healing Tank", "Booby Trap", "Leather Armor"],
                      dev_goals=["Martial Arts I"])
    c = create_player("Charlie", ["Theft", "Armor Break", "Martial Arts I", "Water II", "Earth III",
                                  "Illusions III",
                                  "Circuit III", "Antimagic (Hydro)", "Light II", "Willpower IV"],
                      ["Venom", "Poison Gas", "Face Mask", "Synthetic Weave", "Camo Cloak", "Bokken"],
                      dev_goals=["Sniping"])
    d = create_player("Delta", ["Attunement Detection", "Willpower Detection", "Awareness II", "Theft"],
                      items=["Shrooms", "Medkit"],
                      dev_goals=["Martial Arts I", "Martial Arts II", "Armed Combat I", "Armed Combat II"])
    GAME.advance()

    a.plan_class()
    a.plan_hydro("Mental Reinforcement I")
    a.plan_hydro("Mental Reinforcement II", [1, 2])
    a.plan_hydro("Mental Reinforcement III", [1, 1])
    b.plan_train()
    b.plan_attune(Element.EARTH)
    #c .plan_attack(a)
    # c.plan_attune(Element.ANTI)
    d.plan_steal(a)

    Action.run_turn(GAME)

    for p in [a, b, c, d]:
        print(f"{p.name} Report")
        print(p.get_report())
        if p.tattoo:
            print(get_item(p.tattoo))
        print()

    print(DayReport().generate_report(GAME))


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
