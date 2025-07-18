import json
import random

import combat
from actions import *
from automata import Automata
from constants import Temperament, Condition, NEGATIVE_CONDITIONS
from game import Game
from items import get_item_by_name
from player import Player
from report import get_main_report

GAME = Game()


def create_player(name: str, abilities=None, items=None,
                  dev_goals=None, partial_dev=None,
                  temperament=Temperament.PRIVILEGED,
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

    for ability_name in abilities:
        ability = get_ability_by_name(ability_name)
        devs[ability.pin] = ability.cost
        for skill in ability.get_skills([], [], choice=0):
            if skill.effect == Effect.MAX_WILLPOWER:
                willpower += skill.value
        if ability.pin in [306, 307]:
            continue
        prereq = ability.get_prerequisite()
        while prereq and prereq.pin not in devs:
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
                    items=item_pins, money=5 if temperament == Temperament.LUCRATIVE else 3,
                    willpower=willpower, bounty=2,
                    relative_conditions={}, tattoo=tattoo, concept=None,
                    crafted_before=[],
                    game=GAME)

    if temperament == Temperament.PATIENT:
        GAME.add_event(5, False, 120, player)

    return player


def create_automata(name: str, owner: 'Player', shackled: bool = True) -> Automata:
    return Automata(name=name, owner=owner, conditions=[Condition.LOCKED] if shackled else [], items=[], bounty=0,
                    relative_conditions={}, tattoo=None,
                    game=GAME)


def load(file_prefix: str, turn: int = None, night: bool = None):
    if turn is None or night is None:
        f = open(f"save/{file_prefix}/current.json", 'r')
    else:
        f = open(
            f"save/{file_prefix}/{turn}{'n' if night else 'd'}.json", 'r')
    data = json.load(f)
    global GAME
    GAME = Game()
    GAME.turn = data['turn']
    GAME.night = data['night']
    GAME.events = [tuple(event) for event in data['events']]
    GAME.seed = data['seed']

    for player_name, player_data in data['players'].items():
        player_data['game'] = GAME
        player_data['progress_dict'] = {
            int(k): v for k, v in player_data['progress_dict'].items()}
        player_data['temperament'] = Temperament(
            player_data['temperament'])
        player_data['conditions'] = [
            Condition(_c) for _c in player_data['conditions']]
        player_data['relative_conditions'] = {k: [Condition(_c) for _c in v]
                                              for k, v in player_data['relative_conditions'].items()}
        Player(**player_data)

    for automata_name, automata_data in data['automata'].items():
        automata_data['owner'] = GAME.get_player(automata_data['owner'])
        automata_data['game'] = GAME
        automata_data['conditions'] = [
            Condition(c) for c in automata_data['conditions']]
        automata_data['relative_conditions'] = {k: [Condition(c) for c in v]
                                                for k, v in automata_data['relative_conditions'].items()}

        Automata(**automata_data)


def horn_choice(horn: str):
    return ['fervor', 'fear', 'plenty', 'revelation', 'death'].index(horn.lower())


def conductor_choice(action: str):
    return ['class', 'doctor', 'train', 'bunker', 'shop', 'attack', 'wander'].index(action.lower())


def init():
    create_player("23Starman",
                  ["Attunement Detection", "Willpower Detection", "Circuit II", "Water I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Fire I", "Awareness II"])
    create_player("Anemone",
                  ["Water I", "Fire I", "Toxin"],
                  temperament=Temperament.BLOODTHIRSTY,
                  dev_goals=[])
    create_player("BlackLemonAde",
                  ["Panopticon", "Market Connections I", "Theft"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=[])
    # Befoulment/Miasma/Execute
    create_player("Darklight140",
                  ["Legacy Magic", "Befoulment II", "Martial Arts I"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Armored Combat", "Martial Arts II", "Martial Arts III"])
    create_player("Darkpiplumon",
                  ["Body Reinforcement III"],
                  temperament=Temperament.BLOODTHIRSTY,
                  dev_goals=["Rapid Regen I"])
    # Wilderness/Aegis/Holiday
    create_player("Dragonlord7",
                  ["Legacy Magic", "Wilderness I", "Martial Arts II", "Awareness I"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Martial Arts III", "Wilderness II", "Wilderness III", "Ambush Tactics I"])
    # Random Concept
    create_player("Drasky",
                  ["Incognito I", "Sniping"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=[])
    create_player("Floom",
                  ["Panopticon", "Ambush Tactics I"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Counter Ambush Tactics", "Ambush Tactics II"])
    # Random Concept
    create_player("hotmonkey1",
                  ["Miasma I", "Willpower II", "Crafting I", "Mental Fortification I"],
                  temperament=Temperament.PATIENT,
                  dev_goals=["Will Armor I", "Will Armor II", "Willpower III", "Willpower Draining", "Willpower IV", "Rapid Regen I", "Soul Strike", "Willpower V"])
    # Paperwork/Bureaucracy/Studious
    create_player("Lord of Chromius",
                  ["Legacy Magic", "Paperwork I", "Earth I", "Circuit II"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Water I", "Circuit III", "Earth II", "Mud"])
    create_player("Megaolix",
                  ["Willpower III", "Danger Precognition"],
                  temperament=Temperament.LUCRATIVE,
                  dev_goals=["Mental Fortification I", "Will Armor I", "Willpower IV"])
    create_player("mishtazespy",
                  ["Water III", "Circuit II"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Circuit III", "Air I", "Circuit IV"])
    create_player("NinetyNineLies",
                  ["Crafting II", "Awareness II"],
                  temperament=Temperament.INNOVATIVE,
                  dev_goals=["Bolthole", "Martial Arts I", "Martial Arts II", "Willpower II", "Enhanced Senses",
                             "Martial Arts III",
                             "Armored Combat", "Armed Combat I", "Ambush Tactics I", "Counter Ambush Tactics"])
    # Random Concept
    create_player("Paradosi",
                  ["Crafting II", "Voltage I"],
                  temperament=Temperament.INNOVATIVE,
                  dev_goals=[])
    create_player("PocketRikimaru",
                  ["Ambush Tactics II", "Counter Ambush Tactics", "Willpower I"],
                  temperament=Temperament.SCHOLASTIC,
                  dev_goals=["Body Reinforcement I", "Willpower II", "Body Reinforcement II"])
    # Holiday/Studious/Tiny
    create_player("RyoAtemi",
                  ["Legacy Magic", "Holiday II"],
                  temperament=Temperament.PATIENT,
                  partial_dev={"Holiday III": 5},
                  dev_goals=["Circuit I", "Water I", "Circuit II", "Water II", "Holiday III", "Holiday IV", "Holiday V"])
    create_player("Seventeen",
                  ["Water I", "Fire I", "Toxin"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Martial Arts I", "Martial Arts II"])
    # Random Concept
    create_player("Swift-Sama",
                  ["Aegis I", "Gold"],
                  temperament=Temperament.LUCRATIVE,
                  dev_goals=["Light", "Petrification I", "Awareness I", "Awareness II", "Theft"])
    # Random Concept
    create_player("Tempeljaeger",
                  ["Execute I", "Circuit II", "Earth I", "Fire I"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=[])
    # Random Concept
    create_player("Teyao",
                  ["Eclipse I", "Sniping"],
                  temperament=Temperament.BLOODTHIRSTY,
                  dev_goals=["Armed Combat II"])
    # Studious/Tiny/Wilderness
    create_player("Witherbrine26",
                  ["Legacy Magic", "Tiny II"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Tiny III", "Martial Arts I", "Martial Arts II", "Martial Arts III",
                             "Forged in Fire", "Combat Medicine"])
    # Random Concept
    create_player("Zeal Iskander",
                  ["Suppression II", "Martial Arts III", "Mental Fortification I", "Forged in Fire"],
                  temperament=Temperament.PARANOIAC,
                  dev_goals=[],
                  conditions=[Condition.RINGER])

    # summary(detailed=True)


def summary(detailed=False, condensed=False):
    for player_name, player in GAME.players.items():
        if not player.is_dead():
            if condensed:
                out = f"{player_name} ({player.temperament.name})"
                if player.academics:
                    out += f" [{player.academics} Academics]"
                out += f": {[ability.name for ability in player.get_abilities(include_this_turn=True)]}" \
                    f"({player.get_total_dev()}) "
                if player.willpower:
                    out += f"({player.willpower} Willpower) "
                if player.get_items(duplicates=True):
                    out += f"{[item.name for item in player.get_items(duplicates=True)]}"
                out += f"({player.get_credits()} Credits) "
                if player.condition_debug():
                    out += f"{player.condition_debug()}"
                print(out)
            else:
                out = f"{player_name} ({player.temperament.name})"
                if player.academics:
                    out += f" [{player.academics} Academics]"
                if player.max_willpower:
                    out += f" ({player.willpower}/{player.max_willpower} Willpower)"
                out += f'\n'
                prerequisites = set(ability.get_prerequisite(
                ).name for ability in player.get_abilities(include_this_turn=True) if ability.get_prerequisite())
                if detailed:
                    abilities = sorted([ability for ability in player.get_abilities(
                        include_this_turn=True) if ability.name not in prerequisites], key=lambda x: x.pin)
                    geo_abilities = [
                        ability for ability in abilities if ability.pin < 200]
                    hydro_abilities = [
                        ability for ability in abilities if ability.pin >= 200 and ability.pin < 300]
                    body_abilities = [
                        ability for ability in abilities if ability.pin >= 400 and ability.pin < 500]
                    mind_abilities = [
                        ability for ability in abilities if ability.pin >= 500 and ability.pin < 600]
                    aero_abilities = [
                        ability for ability in abilities if ability.pin >= 600 or (ability.pin >= 300 and ability.pin < 400)]

                    out += f"Abilities ({player.get_total_dev()} Total Progress):\n"
                    if geo_abilities:
                        out += f"  Geo: {', '.join([ability.name for ability in geo_abilities])}\n"
                    if hydro_abilities:
                        out += f"  Hydro: {', '.join([ability.name for ability in hydro_abilities])}\n"
                    if aero_abilities:
                        out += f"  Aero: {', '.join([ability.name for ability in aero_abilities])}\n"
                    if body_abilities:
                        out += f"  Body: {', '.join([ability.name for ability in body_abilities])}\n"
                    if mind_abilities:
                        out += f"  Mind: {', '.join([ability.name for ability in mind_abilities])}\n"

                    partial = [f"{ability.name} ({progress}/{ability.cost})" for (ability, progress) in sorted(player.get_partial_abilities(
                    ), key=lambda x: x[0].pin) if progress != 0]
                    if partial:
                        out += f"  Unfinished: {', '.join(partial)}\n"
                else:
                    out += f"Abilities: {', '.join([ability.name for ability in sorted(player.get_abilities(include_this_turn=True), key=lambda x: x.pin) if ability.name not in prerequisites])} ({player.get_total_dev()} Total Progress)\n"
                out += "Items: "
                if player.get_items_display():
                    out += ', '.join([item + (' x' + str(amount) if amount > 1 or item == "Credits" else '')
                                      for (item, amount) in player.get_items_display()]) + f" ({player.get_total_credit_value()} Total Credit Value)\n"
                    if detailed:
                        items = player.get_items()
                        pins = [item.pin for item in items]
                        if 4201 in pins:
                            if (Condition.CURSE_IMMUNE in player.conditions):
                                # Zweihander owner is immune to curse
                                out += f"  Best Weapon: Zweihander (+0)\n"
                            else:
                                # else its kind of a -2/-2 weapon
                                out += f"  Best Weapon: Zweihander (-2/-2)\n"
                        else:
                            weapons = [(item, skill) for item in items for skill in item.get_skills(
                            ) if skill.effect == Effect.WEAPON]
                            if weapons:
                                best_weapon = max(
                                    weapons, key=lambda x: x[1].value)
                                out += f"  Best Weapon: {best_weapon[0].name} (+{best_weapon[1].value})\n"
                        armors = [(item, skill) for item in items for skill in item.get_skills(
                        ) if skill.effect == Effect.ARMOR]
                        if armors:
                            best_armor = max(armors, key=lambda x: x[1].value)
                            out += f"  Best Armor: {best_armor[0].name} (+{best_armor[1].value})\n"
                else:
                    out += "None\n"
                if player.condition_debug():
                    if detailed:
                        affliction_names = [
                            condition.name for condition in NEGATIVE_CONDITIONS]
                        afflictions = [(condition, amount) for (condition, amount) in player.condition_debug(
                        ).items() if condition in affliction_names]
                        not_afflictions = [(condition, amount) for (condition, amount) in player.condition_debug(
                        ).items() if condition not in affliction_names]
                        out += f"Conditions:\n"
                        if not_afflictions:
                            out += f"  Positive: {', '.join([condition + (' x' + str(amount) if amount > 1 else '') for (condition, amount) in not_afflictions])}\n"
                        if afflictions:
                            out += f"  Negative: {', '.join([condition + (' x' + str(amount) if amount > 1 else '') for (condition, amount) in afflictions])}\n"
                    else:
                        out += f"Conditions: {', '.join([condition + (' x' + str(amount) if amount > 1 else '') for (condition, amount) in  player.condition_debug().items()])}\n"

                print(out)


def get_item_options():
    for i in range(100):
        try:
            item = get_item(i)
            if item.item_type in [ItemType.POTION, ItemType.CONSUMABLE] and item.cost >= 1:
                yield item
        except:
            pass


ITEM_OPTIONS = [item for item in get_item_options()]


def grab_bag(n=3):
    if n<=0:
        return []
    item = random.choice(ITEM_OPTIONS)
    if item.cost > n:
        return grab_bag(n)
    return [item.name] + grab_bag(n-item.cost)


if __name__ == '__main__':
    combat.DEBUG = True  # Shows stats, items, and conditions in reports as public information
    # init()
    # load("test")
    #

    for i in range(20):
        print(grab_bag())

    # a = create_player("Alpha", ["Potion Brewing"], temperament=Temperament.INNOVATIVE)
    # b = create_player("Beta", ["Martial Arts I"], dev_goals=["Martial Arts II"])
    # c = create_player("Charlie", temperament=Temperament.BLOODTHIRSTY)
    # d = create_player("Delta", ["Martial Arts II"])
    # e = create_player("Echo")
    # f = create_player("Foxtrot")
    # a = GAME.get_player("Alpha")
    # b = GAME.get_player("Beta")

    # GAME.add_event(1, False, 120, b)

    # GAME.advance()
    #
    # a.plan_craft("Fire Potion", "Earth Potion")
    # # a.plan_item_target("Pyrite Potion", b)
    # # a.plan_train()
    # b.plan_craft("Fire Potion")
    # # c.plan_shop("Sword")
    # # d.plan_attack(a)
    # # e.plan_attack(a)
    # # f.plan_attack(a)
    #
    # was_alive = [p for p in GAME.players.values() if not p.is_dead()]
    # Action.run_turn(GAME)
    # for p in was_alive:
    #     print(f"{p.name} Report{os.linesep}")
    #     print(p.get_report())
    #     print()

    print(get_main_report().generate_report(GAME))
    # # # # # # #
    summary(detailed=True)

    # GAME.save("test")


# git update-index --assume-unchanged main.py
# git update-index --no-assume-unchanged main.py
