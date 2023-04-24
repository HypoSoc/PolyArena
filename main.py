import json

from actions import *
import combat
from constants import Temperament, Condition
from game import Game
from items import get_item_by_name
from player import Player
from automata import Automata
from report import get_main_report

GAME = Game()


def create_player(name: str, abilities=None, items=None,
                  dev_goals=None, temperament=Temperament.HOT_BLOODED,
                  tattoo=None,
                  conditions=None) -> Player:
    if dev_goals is None:
        dev_goals = []
    if items is None:
        items = []
    if abilities is None:
        abilities = []
    if conditions is None:
        conditions = []
    devs = {}

    willpower = 0

    concept = None

    for ability_name in abilities:
        ability = get_ability_by_name(ability_name)
        if ability.concept:
            concept = ability.concept
        devs[ability.pin] = ability.cost
        for skill in ability.get_skills([], [], choice=0):
            if skill.effect == Effect.MAX_WILLPOWER:
                willpower += skill.value
        if ability.pin in [306, 307]:
            continue
        prereq = ability.get_prerequisite()
        while prereq and prereq.pin not in devs:
            if prereq.concept:
                concept = prereq.concept
            devs[prereq.pin] = prereq.cost
            for skill in prereq.get_skills([], [], choice=0):
                if skill.effect == Effect.MAX_WILLPOWER:
                    willpower += skill.value
            prereq = prereq.get_prerequisite()

    devs = {k: devs[k] for k in sorted(devs.keys())}

    item_pins = []
    for item_names in items:
        item = get_item_by_name(item_names)
        item_pins.append(item.pin)

    dev_list = []
    for dev_name in dev_goals:
        dev_list.append(get_ability_by_name(dev_name).pin)

    if tattoo:
        tattoo = get_item_by_name(tattoo+" Rune").pin

    player = Player(name, devs, dev_list, academics=0, conditions=conditions, temperament=temperament,
                    items=item_pins, money=3, willpower=willpower, bounty=1,
                    relative_conditions={}, tattoo=tattoo, concept=concept,
                    crafted_before=[],
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
            player_data['progress_dict'] = {int(k): v for k, v in player_data['progress_dict'].items()}
            player_data['temperament'] = Temperament(player_data['temperament'])
            player_data['conditions'] = [Condition(c) for c in player_data['conditions']]
            player_data['relative_conditions'] = {k: [Condition(c) for c in v]
                                                  for k, v in player_data['relative_conditions'].items()}
            Player(**player_data)

        for automata_name, automata_data in data['automata'].items():
            automata_data['owner'] = GAME.get_player(automata_data['owner'])
            automata_data['game'] = GAME
            automata_data['conditions'] = [Condition(c) for c in automata_data['conditions']]
            automata_data['relative_conditions'] = {k: [Condition(c) for c in v]
                                                    for k, v in automata_data['relative_conditions'].items()}

            Automata(**automata_data)


def init():
    create_player("Artful Lounger", ["Martial Arts III", "Sniping"], temperament=Temperament.PREPARED,
                  dev_goals=["Armored Combat", "Armed Combat II", "Circuit I", "Water I"],
                  items=["Oblivion Ordinance"])
    create_player("BlueMangoAdea", ["Theft", "Market Connections II"], temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Awareness III", "Trade Secrets", "Copycat"])
    create_player("Megaolix", ["Psy Ops", "Armed Combat II"],
                  temperament=Temperament.PREPARED,
                  dev_goals=["Awareness III", "Theft"],
                  items=["Force Projection", "Bokken"],
                  conditions=[Condition.RINGER])
    create_player("Paradosi", ["Mental Fortification I", "Armed Combat I", "Ambush Tactics I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Counter Ambush Tactics", "Armed Combat II"])
    create_player("PocketRikimaru", ["Conductor I", "Legacy Magic", "Forged in Fire"],
                  temperament=Temperament.PREPARED,
                  dev_goals=["Awareness I", "Conductor II", "Conductor III", "Conductor IV", "Conductor V",
                             "Conductor VI", "Conductor VII"],
                  items=["Synthetic Weave", "Oxygen Mask", "Poison Gas"])
    create_player("Random Anon", ["Martial Arts I", "Awareness III", "Counter Ambush Tactics"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Armed Combat I", "Martial Arts II", "Martial Arts III"])
    create_player("Ricardian", ["Awareness III", "Copycat"], temperament=Temperament.PREPARED,
                  dev_goals=["Attunement Detection", "Willpower Detection", "Theft"],
                  items=["Force Projection", "Booby Trap"])
    create_player("Sargon", ["Panopticon", "Martial Arts I"],
                  temperament=Temperament.PREPARED,
                  dev_goals=["Armed Combat I", "Armored Combat", "Know Thy Enemy", "Psy Ops",
                             "Martial Arts II", "Aeromancy Intuition I"],
                  items=["Bokken", "Force Projection"])
    create_player("Seventeen", ["Hyena III"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Martial Arts I", "Martial Arts II", "Hyena IV"])
    create_player("Songaro", ["Chalk II", "Mental Fortification I"], temperament=Temperament.INTUITIVE)
    create_player("Zeal Iskander", ["Martial Arts III", "Armed Combat II"],
                  temperament=Temperament.PREPARED,
                  dev_goals=["Armored Combat", "Armor Break"],
                  items=["Bokken", "Oxygen Mask", "Poison Gas", "Poison Gas", "Poison Gas", "Poison Gas"])

    summary()


def summary():
    for player_name, player in GAME.players.items():
        if not player.is_dead():
            print(f"{player_name} ({player.temperament.name}) [{player.academics} Academics]: "
                  f"{[ability.name for ability in player.get_abilities()]}({player.get_total_dev()}) "
                  f"{[item.name for item in player.get_items(duplicates=True)]}"
                  f"({player.get_total_credit_value()}) "
                  f"{player.condition_debug()}")
            print()
    print()


def to_conductor_choice(choice):
    return [Class, Doctor, Train, Bunker, Shop, Attack, Wander].index(choice)


if __name__ == '__main__':
    combat.DEBUG = False  # Shows stats, items, and conditions in reports as public information
    # init()

    a = create_player("Alpha", ["Soul Strike"])
    b = create_player("Beta", conditions=[Condition.INJURED], items=["Lizard Tail"])

    GAME.advance()

    a.plan_hydro("Soul Strike", targets=b)
    a.plan_class()
    b.plan_class()

    was_alive = [p for p in GAME.players.values() if not p.is_dead()]

    Action.run_turn(GAME)

    for p in was_alive:
        print(f"{p.name} Report{os.linesep}")
        print(p.get_report())
        print()

    print(get_main_report().generate_report(GAME))
    # # # # # #

    summary()

# git update-index --no-assume-unchanged main.py