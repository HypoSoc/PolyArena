import json

import combat
from actions import *
from automata import Automata
from constants import Temperament, Condition
from game import Game
from items import get_item_by_name
from player import Player
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
                    willpower=willpower, bounty=1,
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
                  ["Crafting I", "Combat Medicine", 'Awareness I'],
                  temperament=Temperament.ALTRUISTIC,
                  dev_goals=["Armored Combat", 'Circuit I', 'Earth I'])
    # Conductor/Stifle/Ooze
    create_player("Anemone",
                  ["Crafting I", "Stifle I", "Legacy Magic"],
                  temperament=Temperament.PARANOIAC,
                  dev_goals=[])
    create_player("BlackLemonAde",
                  ["Circuit II", "Earth I", "Water I", "Magical Healing (Geo)"],
                  temperament=Temperament.ALTRUISTIC,
                  dev_goals=[])
    create_player("Coledon",
                  ["Gold", "Combat Medicine"],
                  temperament=Temperament.ALTRUISTIC,
                  dev_goals=["Water I", "Fire I", "Toxin", "Circuit III", "Circuit IV"])
    # Random Concept
    create_player("DarkLight140",
                  ["Mental Fortification I", 'Gaze II'],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Gaze III"])
    create_player("Dragonlord7",
                  ['Ambush Tactics I', 'Fire II'],
                  temperament=Temperament.BLOODTHIRSTY,
                  dev_goals=["Circuit II", "Cauterization", "Hell Fire", "Fire III", "Circuit III",
                             "Martial Arts I", "Martial Arts II", "Martial Arts III"])
    # Random Concept
    create_player("Drasky",
                  ["Forged in Fire", "Combat Medicine", "Hyena I"],
                  temperament=Temperament.LUCRATIVE,
                  dev_goals=[])
    # Decoy/Bureaucracy/Enfleshed
    create_player("hotmonkey1",
                  ["Rune Crafting II", "Legacy Magic", "Decoy I"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Decoy II", "Decoy III", "Decoy IV", "Fire I", "Fire II", "Circuit III", "Fire III", "Cauterization", "Hell Fire", "Awareness I", "Attunement Detection"])
    # Heliophile/Zweihander/Chalk
    create_player("Lord of Chromius",
                  ["Heliophile II", "Legacy Magic", "Willpower I"],
                  temperament=Temperament.PATIENT,
                  dev_goals=["Mental Fortification I", "Awareness I", "Willpower II", "Ambush Tactics I", "Illusions I", "Heliophile III", "Heliophile IV"])
    create_player("Megaolix",
                  ["Circuit II", "Air II"],
                  partial_dev={'Speed (Geo) I': 5},
                  temperament=Temperament.PATIENT,
                  dev_goals=["Speed (Geo) I", "Speed (Geo) II", "Circuit III", "Fire I", "Fire II"])
    create_player("NinetyNineLies",
                  ["Awareness III", "Copycat", "Counter Ambush Tactics"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Circuit I", "Fire I", "Circuit II", "Air I", "Martial Arts I", "Martial Arts II", "Martial Arts III"])
    create_player("Paradosi",
                  ["Mental Fortification II", "Quiet Casting", "Will Armor I"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Will Armor II", "Awareness I", "Counter Intelligence I"])
    create_player("PocketRikimaru",
                  ["Awareness II", "Copycat", "Ambush Tactics II"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Willpower I", "Body Reinforcement I", "Body Reinforcement II"])
    create_player("RyoAtemi",
                  ["Crafting II", "Willpower II"],
                  temperament=Temperament.INNOVATIVE,
                  dev_goals=["Crafting III", "Willpower III", "Willpower IV", "Awareness I"])
    create_player("Seventeen",
                  ["Sabotage", "Earth I"],
                  temperament=Temperament.ALTRUISTIC,
                  dev_goals=["Profiling", "Willpower Detection", "Know Thy Enemy", "Psy Ops", "Awareness III"])
    # Enfleshed/Yoga/Haruspex
    create_player("Swift-Sama",
                  ["Forged in Fire", "Legacy Magic", "Yoga I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=['Combat Medicine', 'Awareness I', 'Armed Combat I', 'Armed Combat II', 'Martial Arts II', 'Martial Arts III'])
    # Migraine/Augur/Miasma
    create_player("Tempeljaeger",
                  ["Miasma I", "Legacy Magic", "Market Connections II"],
                  temperament=Temperament.PATIENT,
                  dev_goals=[])
    # Random Concept
    create_player("Teyao",
                  ["X", "Circuit II", "Kaleidoscope", 'Nuclear I', 'Ooze I'],
                  temperament=Temperament.SCHOLASTIC,
                  dev_goals=["Nuclear II", "Nuclear III"])
    create_player("Witherbrine26",
                  ["Gold", "Earth I", "Awareness I"],
                  temperament=Temperament.LUCRATIVE,
                  dev_goals=["Earth II", "Circuit III"])
    create_player("Zeal Iskander",
                  ["Theft", "Market Connections I"],
                  partial_dev={'Sabotage': 5},
                  temperament=Temperament.SCHOLASTIC,
                  dev_goals=["Sabotage", "Martial Arts I", "Martial Arts II", "Martial Arts III", "Armored Combat", "Armed Combat I"])

    create_player("Lust",
                  ['Psy Ops', 'Awareness II'],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=['Awareness III', 'Bolthole', 'Circuit I', 'Earth I'])
    create_player("Gluttony",
                  ['Crafting I', 'Bolthole'],
                  temperament=Temperament.PARANOIAC,
                  dev_goals=['Body Reinforcement I', 'Body Reinforcement II', 'Body Reinforcement III', 'Willpower II', 'Willpower III'])
    # Parade/Pinata/Usury
    create_player("Greed",
                  ['Legacy Magic', 'Parade II', 'Circuit I'],
                  temperament=Temperament.LUCRATIVE,
                  dev_goals=['Circuit II', 'Gold', 'Parade III', 'Parade IV', 'Parade V'])
    # Stifle/Snail/Battery
    create_player("Sloth",
                  ['Legacy Magic', 'Snail II'],
                  partial_dev={'Snail III': 5},
                  temperament=Temperament.PATIENT,
                  dev_goals=['Snail III', 'Snail IV', 'Snail V', 'Circuit I', 'Earth I', 'Earth II', 'Circuit II', 'Earth III', 'Circuit III'])
    create_player("Wrath",
                  ['Armed Combat II', 'Sniping'],
                  temperament=Temperament.BLOODTHIRSTY,
                  dev_goals=['Martial Arts II', 'Martial Arts III', 'Armored Combat', 'Forged in Fire'])
    create_player("Envy",
                  ['Copycat', 'Bolthole'],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=['Awareness III'])
    # Shackled/War/Heliophile
    create_player("Pride",
                  ['Lava', 'Earth I', 'Circuit I', 'Fire I', 'Quiet Attune', 'Legacy Magic', 'Shackled II'],
                  temperament=Temperament.PRIVILEGED,
                  conditions=[Condition.RINGER],
                  dev_goals=['Shackled III', 'Shackled IV'])
    # summary()


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


if __name__ == '__main__':
    combat.DEBUG = False  # Shows stats, items, and conditions in reports as public information
    # load("Y19")

    a = create_player("Alpha", ['Decoy I'], items=['Decoy I Rune'])
    b = create_player("Beta")
    c = create_player("Charlie")
    d = create_player("Delta")
    e = create_player("Epsilon")

    GAME.advance()

    a.plan_consume_item("Decoy I Rune")
    a.plan_target("Decoy I", c)
    a.plan_item_target("Decoy I Rune", e)
    b.plan_attack(c)
    d.plan_attack(e)

    was_alive = [p for p in GAME.players.values() if not p.is_dead()]
    Action.run_turn(GAME)
    for p in was_alive:
        print(f"{p.name} Report{os.linesep}")
        print(p.get_report())
        print()

    print(get_main_report().generate_report(GAME))
    # # # # # # #
    summary(detailed=True)

    # GAME.save("Y19")


# git update-index --assume-unchanged main.py
# git update-index --no-assume-unchanged main.py
