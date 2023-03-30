import json

import ability
from actions import *
import combat
from constants import Temperament, Condition
from game import Game
from items import get_item_by_name
from player import Player
from automata import Automata
from report import get_main_report

GAME = Game()


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
        if ability.pin in [306, 307]:
            continue
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
                    items=item_pins, money=3, willpower=willpower, bounty=1,
                    relative_conditions={}, tattoo=tattoo, concept=concept,
                    game=GAME)

    if temperament == Temperament.PATIENT:
        GAME.add_event(5, False, 120, player)

    return player


def create_automata(name: str, owner: 'Player') -> Automata:
    return Automata(name=name, owner=owner, conditions=[], items=[], bounty=0,
                    relative_conditions={}, tattoo=None,
                    game=GAME)


def load(file_prefix: str):
    with open(f"save/{file_prefix}.json", 'r') as f:
        data = json.load(f)
        global GAME
        GAME = Game()
        GAME.turn = data['turn']
        GAME.night = data['night']
        GAME.events = data['events']

        for player_name, player_data in data['players'].items():
            player_data['game'] = GAME
            player_data['progress_dict'] = {int(k): v for k,v in player_data['progress_dict'].items()}
            Player(**player_data)

        for automata_name, automata_data in data['automata'].items():
            automata_data['owner'] = GAME.get_player(automata_data['owner'])
            automata_data['game'] = GAME
            Automata(**automata_data)


if __name__ == '__main__':
    combat.DEBUG = False  # Shows stats, items, and conditions in reports as public information
    # a = create_player("Alpha", ["Willpower V", "Crafting III"],
    #                   ["Healing Tank", "Workbench", "Booby Trap", "Face Mask", "Leather Armor", "Bokken"],
    #                   injured=False)
    # b = create_player("Beta", ["Circuit V", "Earth III", "Awareness I", "Willpower Draining", "Fast Attune II"],
    #                   ["1/2 Medkit", "Poison Gas", "Bunker Shields", "Bunker Munitions", "Venom",
    #                    "Healing Tank", "Booby Trap", "Leather Armor"],
    #                   dev_goals=["Martial Arts I", "Martial Arts II", "Martial Arts III"],
    #                   temperament=Temperament.PATIENT)
    # c = create_player("Charlie", ["Theft", "Unnatural Intuition", "Fast Attune III",
    #                               "Illusions III", "Aeromancy Intuition II", "Speed (Geo) II",
    #                               "Circuit III", "Antimagic (Aero)", "Light II", "Willpower IV"],
    #                   ["Venom", "Poison Gas", "Face Mask", "Camo Cloak", "Bokken"],
    #                   dev_goals=[])
    # d = create_player("Delta", ["Attunement Detection", "Willpower Detection", "Know Thy Enemy",
    #                             "Awareness II", "Theft", "Aeromancy Intuition I"],
    #                   items=["Shrooms", "Medkit"],
    #                   dev_goals=["Aeromancy Intuition II"], temperament=Temperament.PATIENT)
    load("test")

    GAME.advance()

    a = GAME.get_player("Alpha")
    b = GAME.get_player("Beta")
    c = GAME.get_player("Charlie")
    d = GAME.get_player("Delta")
    f = GAME.get_player("Fred")

    a.plan_hydro("Crafting III")
    a.plan_craft("Sword", "Leather Armor")
    a.plan_trade(c, item_names=["Sword", "Leather Armor"])
    b.plan_attack(f)
    c.plan_attack(f)

    Action.run_turn(GAME)

    for p in GAME.players.values():
        if not p.is_dead():
            print(f"{p.name} Report")
            print(p.get_report())
            print()

    print(get_main_report().generate_report(GAME))

    GAME.save("test")


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
