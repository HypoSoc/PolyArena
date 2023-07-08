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
                  dev_goals=None, partial_dev=None,
                  temperament=Temperament.HOT_BLOODED,
                  tattoo=None,
                  conditions=None) -> Player:
    if dev_goals is None:
        dev_goals = []
    if partial_dev is None:
        partial_dev = {}
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

    for ability_name, points in partial_dev.items():
        ability = get_ability_by_name(ability_name)
        devs[ability.pin] = points

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
        GAME.events = [tuple(event) for event in data['events']]
        GAME.seed = data['seed']

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
    create_player("23Starman", ["Armed Combat II", "Martial Arts II", "Awareness I", "Air II"],
                  temperament=Temperament.HOT_BLOODED, conditions=[Condition.RINGER],
                  dev_goals=["Martial Arts III", "Forged in Fire", "Sniping"])
    create_player("BlackLemonAde", ["Will Armor II", "Armored Combat"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Willpower III", "Awareness I", "Willpower Detection", "Willpower Draining"])
    create_player("boyboy180", ["Edifice I", "Legacy Magic", "Water I"],
                  partial_dev={"Magical Healing (Geo)": 5},
                  temperament=Temperament.ALTRUISTIC,
                  dev_goals=["Magical Healing (Geo)", "Circuit II", "Circuit III", "Fast Attune I",
                             "Water II", "Fast Attune II", "Water III"])
    create_player("Darkpiplumon", ["Fire I", "Ambush Tactics I", "Haruspex I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Awareness II", "Martial Arts I", "Haruspex II"])
    create_player("Dragonlord7", ["Lava", "Fire I", "Earth I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Martial Arts I", "Armed Combat I", "Earth II", "Circuit III",
                             "Earth III", "Sniping", "Armed Combat II"])
    create_player("Lord of Chromius", ["Mystic Penetration"],
                  temperament=Temperament.SCHOLASTIC,
                  dev_goals=["Rapid Regen I", "Willpower III", "Will Armor I", "Sniping (Hydro)"])
    create_player("M3mentoMori", ["Horn III"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Martial Arts I", "Martial Arts II", "Armed Combat I", "Armored Combat"])
    create_player("Megaolix", ["Armed Combat II", "Ambush Tactics I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Counter Ambush Tactics", "Awareness II"])
    create_player("Paradosi", ["Air III", "Speed (Geo) I"],
                  temperament=Temperament.INTUITIVE, conditions=[Condition.RINGER],
                  dev_goals=["Circuit II", "Circuit III"])
    create_player("Papa Loa", ["Crafting I", "Augur I", "Legacy Magic"],
                  temperament=Temperament.PARANOIAC,
                  dev_goals=["Crafting II", "Augur II"])
    create_player("RyoAtemi", ["Befoulment I", "Legacy Magic", "Awareness II", "Counter Intelligence I"],
                  partial_dev={"Trade Secrets": 5},
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Trade Secrets", "Copycat", "Awareness III",
                             "Befoulment II", "Befoulment III", "Befoulment IV"])
    create_player("Seventeen", ["Ambush Tactics II", "Counter Ambush Tactics", "Martial Arts II"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Awareness II", "Armed Combat I", "Know Thy Enemy",
                             "Armed Combat II"])
    create_player("Teyao", ["Air II", "Circuit II", "Speed (Geo) I"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Speed (Geo) II", "Circuit III", "Fire I"])
    create_player("Witherbrine26", ["Panopticon"],
                  partial_dev={"Know Thy Enemy": 5},
                  temperament=Temperament.SCHOLASTIC,
                  dev_goals=["Know Thy Enemy", "Psy Ops"])

    # Bounty Hunter
    create_player("Apple", ["Unnatural Intuition", "Body Reinforcement II"], temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Willpower II", "Willpower III", "Willpower IV", "Soul Strike"])
    # Nerd
    create_player("Comrade", ["Snail III"], temperament=Temperament.PATIENT,
                  dev_goals=["Awareness I", "Awareness II", "Awareness III", "Panopticon"])
    # Info Broker
    create_player("Liquid", ["Awareness II", "Attunement Detection", "Willpower Detection",
                             "Aeromancy Intuition I", "Market Connections I"], temperament=Temperament.SCHOLASTIC,
                  dev_goals=["Bolthole", "Know Thy Enemy", "Psy Ops"])
    # Healbot
    create_player("Quaestor", ["Combat Medicine", "Forged in Fire", "Martial Arts II"],
                  temperament=Temperament.LUCRATIVE,
                  dev_goals=["Armored Combat", "Circuit I", "Earth I", "Earth II",
                             "Circuit II", "Earth III", "Circuit III"])
    # Bully
    create_player("Teeter", ["Petrification I", "Light I", "Speed (Geo) I"], temperament=Temperament.INTUITIVE,
                  dev_goals=["Martial Arts I", "Armed Combat I", "Armor Break"])
    # Nerd
    create_player("Zippy", ["Eclipse II", "Mental Fortification II"], temperament=Temperament.PRIVILEGED,
                  dev_goals=["Willpower II", "Enhanced Senses", "Danger Precognition", "Willpower III", "Rapid Regen I"])

    # summary()


def summary():
    for player_name, player in GAME.players.items():
        if not player.is_dead():
            out = f"{player_name} ({player.temperament.name})"
            if player.academics:
                out += f" [{player.academics} Academics]"
            out += f": {[ability.name for ability in player.get_abilities(include_this_turn=True)]}" \
                   f"({player.get_total_dev()}) "
            if player.willpower:
                out += f"({player.willpower} Willpower) "
            if player.get_items(duplicates=True):
                out += f"{[item.name for item in player.get_items(duplicates=True)]}"
            out += f"({player.get_total_credit_value()} Credit Value) "
            if player.condition_debug():
                out += f"{player.condition_debug()}"
            print(out)
            print()
    print()


def to_conductor_choice(choice):
    return [Class, Doctor, Train, Bunker, Shop, Attack, Wander].index(choice)


def to_horn_choice(choice):
    return ["fervor", "fear", "plenty", "revelation", "death"].index(choice.lower())


if __name__ == '__main__':
    combat.DEBUG = False  # Shows stats, items, and conditions in reports as public information

    load("Y9")

    bla = GAME.get_player("BlackLemonAde")
    boy = GAME.get_player("boyboy180")
    dark = GAME.get_player("Darkpiplumon")
    dragon = GAME.get_player("Dragonlord7")
    lord = GAME.get_player("Lord of Chromius")
    m3mento = GAME.get_player("M3mentoMori")
    mega = GAME.get_player("Megaolix")
    para = GAME.get_player("Paradosi")
    papa = GAME.get_player("Papa Loa")
    ryo = GAME.get_player("RyoAtemi")
    seventeen = GAME.get_player("Seventeen")
    star = GAME.get_player("23Starman")
    teyao = GAME.get_player("Teyao")
    wither = GAME.get_player("Witherbrine26")

    apple = GAME.get_player("Apple")
    comrade = GAME.get_player("Comrade")
    liquid = GAME.get_player("Liquid")
    quae = GAME.get_player("Quaestor")
    teeter = GAME.get_player("Teeter")
    zip = GAME.get_player("Zippy")

    GAME.advance()

    # boy.plan_consume_item("Shrooms")
    boy.plan_attune(Element.WATER)
    boy.plan_bunker()
    # # # # # # # boy.set_dev_plan("Circuit III", "Edifice II", "Edifice III", "Edifice IV")
    # # # # # # # # # # # # boy.plan_trade(dark, money=1)
    # # # # # # # # # # # # Nerd (M3mentoMori)
    # comrade.plan_consume_item("Poison Gas")
    comrade.plan_attune(Element.EARTH)
    # comrade.plan_class()
    comrade.plan_target("Snail I", comrade)
    # # # # # comrade.plan_attack(mega)
    # # # # # comrade.set_dev_plan("Circuit II", "Air I")
    # # # # # # # # # # # # Heal bot (Lord of Chromius)
    # # quae.plan_consume_item("Poison Gas")
    quae.plan_attack(boy)
    # quae.plan_train()
    # quae.plan_class()
    # quae.plan_trade(comrade, item_names=["Poison Gas"])
    # # quae.plan_shop("Sword", "Oxygen Mask", "Camo Cloak", "Soft", "Poison Gas", "Poison Gas")
    # # # # # quae.set_dev_plan("Armed Combat I", "Circuit I", "Fire I", "Circuit II")

    was_alive = [p for p in GAME.players.values() if not p.is_dead()]

    Action.run_turn(GAME)

    for p in was_alive:
        print(f"{p.name} Report{os.linesep}")
        print(p.get_report())
        print()

    print(get_main_report().generate_report(GAME))
    # # # # # # # # #
    summary()
    GAME.save("Y9")

# git update-index --assume-unchanged main.py
# git update-index --no-assume-unchanged main.py