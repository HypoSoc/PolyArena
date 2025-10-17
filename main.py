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

    player = Player(name, devs, dev_list, academics=0, conditions=conditions, temperaments=[temperament],
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
        player_data['temperaments'] = [Temperament(_t) for _t in player_data['temperaments']]
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
    create_player("BlackLemonAde",
                  ["Ambush Tactics I", "Attunement Detection", "Willpower Detection", "Armed Combat I"],
                  dev_goals=["Counter Ambush Tactics", "Awareness II", "Aeromancy Intuition", "Armed Combat II"],
                  temperament=Temperament.BLOODTHIRSTY,
                  items=['Pyrite Potion', 'Fire Potion', 'Earth Potion'])

    create_player("Darklight140",
                  ["Illusions I", "Martial Arts III"],
                  dev_goals=["Armored Combat", "Augmented Combat", "Illusions II", "Illusions III"],
                  temperament=Temperament.SCHOLASTIC,
                  items=['Pyrite Potion', 'Earth Potion', 'Fire Potion'])

    # Parade/War/Shackled
    create_player("Darkpiplumon",
                  ["Shackled II", "Legacy Magic", "Martial Arts II"],
                  dev_goals=["Martial Arts III", "Shackled III"],
                  temperament=Temperament.SCHOLASTIC,
                  items=['Mud Potion', 'Pyrite Potion', 'Earth Potion'])

    # Libra/War/Rapier
    create_player("hotmonkey1",
                  ["War II", "Legacy Magic", "Martial Arts I"],
                  dev_goals=[],
                  temperament=Temperament.BLOODTHIRSTY,
                  items=['Pyrite Potion', 'Fire Potion', 'Earth Potion'])

    # Libra/Hyena/Zweihander
    create_player("Lord of Chromius",
                  ["Hyena II", "Legacy Magic", "Martial Arts I"],
                  partial_dev={"Hyena III": 5},
                  dev_goals=["Hyena III", "Martial Arts II", "Martial Arts III", "Awareness I", "Ambush Tactics I", "Armed Combat I"],
                  temperament=Temperament.INTUITIVE,
                  items=['Paperwork', 'Earth Potion', 'Pyrite Potion'])

    create_player("Megaolix",
                  ["Martial Arts III", "Forged in Fire", "Awareness I"],
                  dev_goals=[],
                  temperament=Temperament.STUBBORN,
                  items=['Mud Potion', 'Fire Potion', 'Pyrite Potion'])

    create_player("Nightfire",
                  ["Will Armor II", "Mental Fortification I"],
                  partial_dev={"Mental Fortification II": 5},
                  dev_goals=["Mental Fortification II"],
                  temperament=Temperament.STUBBORN,
                  items=['Earth Potion', 'Fire Potion', 'Paperwork'])

    create_player("NinetyNineLies",
                  ["Ash", "Fire I", "Air I"],
                  dev_goals=["Circuit III", "Water I", "Toxin", "Earth I", "Dust", "Circuit IV"],
                  temperament=Temperament.BLOODTHIRSTY,
                  items=['Fire Potion', 'Pyrite Potion', 'Mud Potion'])

    # Libra/Rapier/Suppression
    create_player("Paradosi",
                  ["Rapier II", "Legacy Magic", "Martial Arts I"],
                  dev_goals=[],
                  temperament=Temperament.PSYCHO,
                  items=['Earth Potion', 'Paperwork', 'Pyrite Potion'])

    create_player("PocketRikimaru",
                  ["Circuit II", "Fire II"],
                  partial_dev={"Fire III": 5},
                  dev_goals=["Fire III", "Martial Arts I", "Martial Arts II",],
                  temperament=Temperament.HOT_BLOODED,
                  items=['Earth Potion', 'Paperwork', 'Fire Potion'])

    create_player("RyoAtemi",
                  ["Copycat", "Awareness III"],
                  dev_goals=["Market Connections I", "Market Connections II",
                             "Counter Intelligence I", "Counter Intelligence II", "Bolthole"],
                  temperament=Temperament.STUBBORN,
                  items=['Paperwork', 'Pyrite Potion', 'Mud Potion'])

    create_player("Swift-Sama",
                  ["Stifle I", "Mental Fortification II", "Rapid Regen I", "Body Reinforcement I", "Willpower II"],
                  dev_goals=["Body Reinforcement II", "Body Reinforcement III", "Willpower III",
                             "Willpower IV", "Rapid Regen II", "Soul Strike"],
                  temperament=Temperament.SCHOLASTIC,
                  conditions=[Condition.RINGER],
                  items=['Earth Potion', 'Mud Potion', 'Paperwork'])

    create_player("Tempeljaeger",
                  ["Earth I", "Water I", "Mud"],
                  dev_goals=["Earth II", "Circuit III", "Martial Arts I"],
                  temperament=Temperament.PATIENT,
                  items=['Earth Potion', 'Mud Potion', 'Paperwork'])

    create_player("Teyao",
                  ["Crafting II"],
                  partial_dev={"Crafting III": 10},
                  dev_goals=["Crafting III", "Willpower II", "Willpower III", "Willpower IV", "Willpower V",],
                  temperament=Temperament.INNOVATIVE,
                  items=['Fire Potion', 'Mud Potion', 'Paperwork'])

    # Libra/Rapier/Suppression
    create_player("Witherbrine26",
                  ["Zweihander I", "Legacy Magic", "Martial Arts III"],
                  dev_goals=[],
                  temperament=Temperament.HOT_BLOODED,
                  items=['Paperwork', 'Pyrite Potion', 'Fire Potion'])

    create_player("Zeal Iskander",
                  ["Water I", "Fire I", "Toxin"],
                  dev_goals=[],
                  temperament=Temperament.HOT_BLOODED,
                  items=['Fire Potion', 'Earth Potion', 'Mud Potion'])

    # summary(detailed=True)


def summary(detailed=False, condensed=False):
    for player_name, player in GAME.players.items():
        if not player.is_dead():
            if condensed:
                out = f"{player_name} ({player.get_temperament_display()})"
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
                out = f"{player_name} ({player.get_temperament_display()})"
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


ITEM_OPTIONS = [get_item_by_name(item) for item in ["Venom", "Medkit", "Fire Potion", "Earth Potion", "Frost Potion", "Mud Potion", "Pyrite Potion", "Soft", "Lizard Tail", "Leather Armor", "Face Mask", "Network Spike"]]


def grab_bag(n=3):
    if n<=0:
        return []
    item = random.choice(ITEM_OPTIONS)
    if item.cost > n:
        return grab_bag(n)
    return [item.name] + grab_bag(n-item.cost)


PM = {
}


if __name__ == '__main__':
    combat.DEBUG = False  # Shows stats, items, and conditions in reports as public information
    # init()

    load("Y28")
    #

    bla = GAME.get_player('BlackLemonAde')
    dark = GAME.get_player('Darklight140')
    darp = GAME.get_player('Darkpiplumon')
    hot = GAME.get_player('hotmonkey1')
    lord = GAME.get_player('Lord of Chromius')
    mega = GAME.get_player('Megaolix')
    night = GAME.get_player('Nightfire')
    nine = GAME.get_player('NinetyNineLies')
    para = GAME.get_player('Paradosi')
    pocket = GAME.get_player('PocketRikimaru')
    ryo = GAME.get_player('RyoAtemi')
    swift = GAME.get_player('Swift-Sama')
    tempel = GAME.get_player('Tempeljaeger')
    teyao = GAME.get_player('Teyao')
    wither = GAME.get_player('Witherbrine26')
    zeal = GAME.get_player('Zeal Iskander')

    GAME.advance()


    # hot.set_dev_plan("Martial Arts III", "Armed Combat I")
    # # # # # hot.plan_consume_item("Fire Potion", "Earth Potion")
    # # # hot.plan_shop("Synthetic Weave")
    # hot.plan_target("War II", hot)
    # hot.plan_attack(mega)
    # hot.plan_trade(mega, money=5)
    # hot.plan_attack(night)
    hot.plan_consume_item("Liquid Memories")

    # # # # # # # # # # mega.set_dev_plan("Armored Combat", "Combat Medicine", "Profiling")
    # # mega.plan_attack(ryo)
    # # # # mega.plan_class()
    # mega.plan_shop("Liquid Memories", "Liquid Memories", "Cheat Sheet")
    # mega.plan_trade(hot, item_names=["Liquid Memories"])
    mega.plan_consume_item("Liquid Memories", "Cheat Sheet")

    # # # # # # night.set_dev_plan("Awareness I", "Willpower III", "Body Reinforcement I")
    # night.plan_hydro("Mental Fortification II", will=[0,2])
    # # night.plan_hydro("Will Armor II", contingency=True)
    # # # # # # # night.plan_consume_item("Poison Gas", "Shrooms")
    # # # # # # # night.plan_attack(pocket)
    # # night.plan_bunker()
    # night.plan_class()
    

    # # # # # # # # ryo.plan_consume_item("Pyrite Potion", "Paperwork")
    # # # # # # # # ryo.plan_item_target("Pyrite Potion", nine)
    # # # # # # # # # # ryo.plan_shop("Oxygen Mask")
    # # ryo.plan_spy(hot, mega)
    # # # # ryo.plan_shop("Bokken", "Leather Armor")
    # # # # ryo.plan_trade(para, item_names=["Bokken", "Leather Armor"])
    # ryo.plan_attack(hot)

    was_alive = [p for p in GAME.players.values() if not p.is_dead()]
    Action.run_turn(GAME)
    for p in was_alive:
        print(f"https://forums.spacebattles.com/conversations/{PM[p.name]}/")
        print(f"{p.name} Report{os.linesep}")
        print(p.get_report())
        print()

    print(get_main_report().generate_report(GAME))
    # # # # # # #
    summary(detailed=True)

    # GAME.save("Y28")


# git update-index --assume-unchanged main.py
# git update-index --no-assume-unchanged main.py
