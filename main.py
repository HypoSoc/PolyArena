from actions import *
import combat
from constants import Temperament, Condition
from game import Game
from items import get_item_by_name
from player import Player
from automata import Automata
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

    concept = None

    for ability_name in abilities:
        ability = get_ability_by_name(ability_name)
        if ability.concept:
            concept = ability.concept
        devs[ability.pin] = ability.cost
        for skill in ability.get_skills([], []):
            if skill.effect == Effect.MAX_WILLPOWER:
                willpower += skill.value
        prereq = ability.get_prerequisite()
        while prereq and prereq.pin not in devs:
            if prereq.concept:
                concept = prereq.concept
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
                    items=item_pins, money=10, willpower=willpower, bounty=0,
                    relative_conditions={}, tattoo=tattoo, concept=concept,
                    game=GAME)

    def patient():
        Action.progress(player, 20)

    if temperament == Temperament.PATIENT:
        GAME.add_event(5, False, patient)

    return player


def create_automata(name: str, owner: 'Player') -> Automata:
    return Automata(name=name, owner=owner, conditions=[], items=[], bounty=0,
                    relative_conditions={}, tattoo=None,
                    game=GAME)


if __name__ == '__main__':
    combat.DEBUG = True  # Shows stats, items, and conditions in reports as public information
    a = create_player("Alpha", ["Willpower V", "Crafting III", "Dummy Concept III", "Reality Imposition"],
                      ["Healing Tank", "Workbench", "Booby Trap", "Fire II Rune", "Leather Armor", "Bokken"],
                      injured=True)
    b = create_player("Beta", ["Circuit V", "Earth III", "Awareness I", "Willpower Draining", "Light II"],
                      ["1/2 Medkit", "Poison Gas", "Bunker Shields", "Bunker Munitions", "Venom",
                       "Healing Tank", "Booby Trap", "Leather Armor"],
                      dev_goals=["Martial Arts I"])
    c = create_player("Charlie", ["Theft", "Armor Break", "Martial Arts I", "Water II", "Earth III",
                                  "Illusions III",
                                  "Circuit III", "Antimagic (Hydro)", "Light II", "Willpower IV"],
                      ["Venom", "Poison Gas", "Face Mask", "Synthetic Weave", "Camo Cloak", "Bokken"],
                      dev_goals=["Sniping"])
    d = create_player("Delta", ["Attunement Detection", "Willpower Detection",
                                "Awareness II", "Theft", "Market Connections II"],
                      items=["Shrooms", "Medkit"],
                      dev_goals=["Martial Arts I", "Martial Arts II", "Armed Combat I", "Armed Combat II"])

    e = create_automata("ROBO_ALPHA", a)

    GAME.advance()

    a.plan_hydro("Crafting III")
    a.plan_shop("Automata", "Automata", automata_name=['DAVE', "Betsy"])
    a.plan_trade(c, automata=['DAVE', e], item_name_condition=(c, 3, []))
    b.plan_train()
    b.plan_attune(Element.EARTH)
    c.plan_attune(Element.ANTI)
    c.plan_trade(a, money=3, item_name_condition=(a,0,["Automata", "Automata"]))
    e.plan_craft("Automata", automata_name='DAVID')

    Action.run_turn(GAME)

    for p in [a, b, c, d]:
        print(f"{p.name} Report")
        print(p.get_report())
        if p.concept:
            print(p.concept)
        print()

    print(DayReport().generate_report(GAME))


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
