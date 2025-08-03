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
    # Bureaucracy/Paperwork/Fraud
    create_player("23Starman",
                  ["Crafting I", "Legacy Magic", "Fraud I"],
                  temperament=Temperament.INNOVATIVE,
                  partial_dev={"Crafting II": 5},
                  dev_goals=["Crafting II"],
                  items=['Frost Potion', 'Fire Potion', 'Mud Potion'])
    create_player("A Nice Girl",
                  ["Rune Crafting I", "Earth II"],
                  temperament=Temperament.INNOVATIVE,
                  dev_goals=["Air I", "Awareness I", "Magical Healing (Geo)", "Dust", "Rune Crafting II"],
                  items=['Medkit', 'Rubber Potion'])
    create_player("Anemone",
                  ["Awareness III", "Poisoning", "Potion Brewing"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=[],
                  items=['Mud Potion', 'Pyrite Potion', 'Rubber Potion'])
    create_player("Amonclone4321",
                  ["Ash", "Fire I", "Air I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Earth I", "Circuit III", "Dust"],
                  items=['Pyrite Potion', 'Medkit'])
    create_player("Axeorthedark",
                  ["Martial Arts III", "Willpower II", "Body Reinforcement I"],
                  temperament=Temperament.STUBBORN,
                  dev_goals=[],
                  items=['Cheat Sheet', 'Earth Potion'])
    create_player("BlackLemonAde",
                  ["Counter Ambush Tactics", "Aeromancy Intuition", "Armed Combat I"],
                  temperament=Temperament.BLOODTHIRSTY,
                  dev_goals=[],
                  items=['Mud Potion', 'Earth Potion', 'Venom'])
    # Random Concept
    create_player("ButterGod",
                  ["Martial Arts III", "Armed Combat I", "Libra I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Armed Combat II", "Awareness I", "Awareness II"],
                  items=['Fire Potion', 'Venom', 'Venom'])
    create_player("DarkLight140",
                  ["Martial Arts III", "Sniping"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Awareness I", "Awareness II"],
                  items=['Cheat Sheet', 'Venom'])
    create_player("Darkpiplumon",
                  ["Martial Arts III", "Resonance I", "legacy Magic"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Circuit I", "Earth I"],
                  items=['Medkit', 'Rubber Potion'])
    create_player("Drasky",
                  ["Legacy Magic", "Decoy I", "Forged in Fire"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Decoy II", "Decoy III", "Martial Arts II"],
                  items=['Fire Potion', 'Frost Potion', 'Rubber Potion'])
    create_player("Floom",
                  ["Water III", "Circuit II"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Circuit III", "Martial Arts I", "Martial Arts II", "Martial Arts III"],
                  items=['Shrooms', 'Venom'])
    create_player("hotmonkey1",
                  ["Panopticon", "Market Connections II", "Counter Intelligence I"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Theft", "Willpower Detection", "Profiling", "Potion Brewing"],
                  items=['Shrooms', 'Venom'])
    create_player("Lord of Chromius",
                  ["Fire I", "Earth I", "Circuit III"],
                  temperament=Temperament.INTUITIVE,
                  partial_dev={"Earth II": 5},
                  dev_goals=["Earth II", "Cauterization", "Willpower I", "Willpower II", "Willpower III", "Reinforced Will"],
                  items=["Venom", "Cheat Sheet"])
    create_player("Megaolix",
                  ["Earth II", "Petrification I"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Circuit II", "Circuit III", "Air I", "Dust", "Quiet Attune", "Speed (Geo) I", "Petrification II"],
                  items=['Medkit', 'Fire Potion'])
    create_player("mishtazespy",
                  ["Light", "Combat Regeneration (Geo)"],
                  temperament=Temperament.ALTRUISTIC,
                  dev_goals=["Circuit II", "Kaleidoscope", "Cauterization", "Hell Fire", "Speed (Geo) I"],
                  items=['Medkit', 'Pyrite Potion'])
    create_player("NinetyNineLies",
                  ["Crafting I", "Combat Medicine", "Forged in Fire"],
                  temperament=Temperament.STUBBORN,
                  dev_goals=["Awareness I", "Potion Brewing", "Martial Arts II", "Martial Arts III", "Armored Combat"],
                  items=['Medkit', 'Poison Gas'])
    create_player("Paradosi",
                  ["Water II"],
                  partial_dev={"Water III": 10},
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Water III", "Circuit II", "Circuit III", "Rune Crafting I", "Runic Tattoos"],
                  items=['Shrooms', 'Venom'])
    create_player("Raron",
                  ["Willpower II", "Body Reinforcement II", "Mental Fortification I"],
                  temperament=Temperament.BLOODTHIRSTY,
                  dev_goals=["Rapid Regen I", "Will Armor I", "Will Armor II", "Speed (Hydro) I"],
                  items=['Fire Potion', 'Mud Potion', 'Fire Potion'])
    create_player("RyoAtemi",
                  ["Air I", "Martial Arts III", "Armored Combat"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Circuit II", "Air II"],
                  items=['Venom', 'Frost Potion', 'Venom'])
    create_player("Seventeen",
                  ["Will Blades", "Ambush Tactics I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Mystic Penetration", "Counter Ambush Tactics", "Ambush Tactics II"],
                  items=['Poison Gas', 'Mud Potion', 'Earth Potion'])
    # Kindness/Haruspex/Quackery
    create_player("Swift-Sama",
                  ["Kindness II", "Legacy Magic", "Awareness I"],
                  temperament=Temperament.ALTRUISTIC,
                  dev_goals=["Potion Brewing", "Awareness II", "Sabotage"],
                  items=['Rubber Potion', 'Venom', 'Mud Potion'])
    create_player("Tempeljaeger",
                  ["Fire II", "Circuit II", "Air I"],
                  temperament=Temperament.BLOODTHIRSTY,
                  dev_goals=["Fire III", "Circuit III", "Circuit IV", "Ash", "Awareness I", "Ambush Tactics I"],
                  items=['Shrooms', 'Fire Potion'])
    create_player("Teyao",
                  ["Theft", "Awareness III", "Profiling"],
                  temperament=Temperament.LUCRATIVE,
                  dev_goals=["Panopticon", "Bolthole", "Poisoning"],
                  items=["Shrooms", "Frost Potion"])
    create_player("unrideableHorse",
                  ["Martial Arts II", "Ambush Tactics II"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Martial Arts III", "Awareness II", "Awareness III", "Panopticon"],
                  items=['Rubber Potion', 'Shrooms'])
    create_player("Witherbrine26",
                  ["Air III", "Circuit II"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Circuit III", "Awareness I"],
                  items=['Rubber Potion', 'Frost Potion', 'Frost Potion'])
    create_player("Zeal Iskander",
                  ["Soul Strike"],
                  temperament=Temperament.ALTRUISTIC,
                  dev_goals=["Willpower V", "Rapid Regen I"],
                  items=['Shrooms', 'Fire Potion'])

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


ITEM_OPTIONS = [item for item in get_item_options()]


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
    load("Y25")
    #
    star = GAME.get_player("23Starman")
    girl = GAME.get_player("A Nice Girl")
    anemone = GAME.get_player("Anemone")
    amon = GAME.get_player("Amonclone4321")
    axe = GAME.get_player("Axeorthedark")
    bla = GAME.get_player("BlackLemonAde")
    butter = GAME.get_player("ButterGod")
    darklight = GAME.get_player("DarkLight140")
    darpi = GAME.get_player("Darkpiplumon")
    drasky = GAME.get_player("Drasky")
    floom = GAME.get_player("Floom")
    hotmonkey = GAME.get_player("hotmonkey1")
    lord = GAME.get_player("Lord of Chromius")
    mega = GAME.get_player("Megaolix")
    mish = GAME.get_player("mishtazespy")
    nine = GAME.get_player("NinetyNineLies")
    para = GAME.get_player("Paradosi")
    raron = GAME.get_player("Raron")
    ryo = GAME.get_player("RyoAtemi")
    seventeen = GAME.get_player("Seventeen")
    swift = GAME.get_player("Swift-Sama")
    tempel = GAME.get_player("Tempeljaeger")
    teyao = GAME.get_player("Teyao")
    unrideable = GAME.get_player("unrideableHorse")
    wither = GAME.get_player("Witherbrine26")
    zeal = GAME.get_player("Zeal Iskander")

    lemon = GAME.get_player("1WholeLemons")

    # for i in range(20):
    #     print(grab_bag())

    GAME.advance()

    # # # girl.set_dev_plan("Speed (Geo) I", "Dust", "Rune crafting II", "Fire I", "Runic Tattoos")
    girl.plan_attune(Element.AIR, Element.EARTH)
    # # # # # girl.plan_consume_item("Air I Rune", "Circuit II Rune")
    girl.plan_bunker()
    # girl.plan_trade(wither, item_names=["Earth II Rune"])
    # # # girl.plan_shop("Sword")
    # # # # # # # # girl.plan_trade(hotmonkey, item_names=["Earth II Rune"])
    # # # anemone.set_dev_plan("Bolthole")
    # # # # # # anemone.plan_consume_item("Poison Gas")
    # # # # # # anemone.plan_craft("Fire Potion")
    # # # anemone.plan_bunker()
    # # # # # # # anemone.plan_attack(darklight)
    # # # # # # # # # anemone.plan_shop("Gas Mask", "Poison Gas", "Poison Gas")
    # # # # # anemone.plan_trade(tempel, item_names=["Frost Potion"])
    # # # # # # anemone.plan_spy(darpi, axe)
    # # # # # # anemone.plan_trade(amon, item_names=["Fire Potion"])
    # # # # # # anemone.plan_trade(darklight, money=1)
    # # # axe.plan_hydro("Body Reinforcement I", will=[0,1], contingency=False)
    # # # # # # # axe.set_dev_plan("Forged in Fire")
    # # # axe.plan_train()
    # butter.set_dev_plan("Libra II")
    # # # # # # butter.plan_consume_item("Fire Potion")
    # butter.plan_attack(tempel)
    # # # # # # butter.plan_trade(amon, item_names=["Sword"], item_name_condition=(amon, 1, []))
    # # # # # # # # hotmonkey.set_dev_plan("Bolthole", "Willpower Detection", "Profiling")
    # # hotmonkey.plan_fake_ability("Willpower Detection")
    # hotmonkey.plan_steal(girl)
    # # hotmonkey.plan_consume_item("Earth Potion", "Earth II Rune", "Pyrite Potion")
    # # hotmonkey.plan_item_target("Pyrite Potion", axe)
    # # # # # # # # # hotmonkey.plan_fake_action(Train(None, hotmonkey))
    # # # # # # hotmonkey.plan_shop("Force Projection", "Ablative Ossification", "Poison Gas")
    # # # # hotmonkey.plan_craft("Earth Potion", "Pyrite Potion")
    # # # # # hotmonkey.plan_trade(tempel, item_names=["Fire Potion"])
    # # # # # # # # # # # mish.plan_consume_item("Shrooms")
    # # # # # # # # # # mish.set_dev_plan("Cauterization", "Hell Fire", "Speed (Geo) I", "Speed (Geo) II")
    # # mish.plan_attune(Element.LIGHT, Element.LIGHT)
    # # mish.plan_attack(hotmonkey)
    # # # # # mish.plan_trade(butter, money=1)
    # # # # # # # # mish.plan_bounty(amon, amount=3)
    # # # # # # # # # # # mish.plan_trade(butter, item_names=["Medkit"], item_name_condition=(butter, 1, ["venom"]))
    # # # # # # # # nine.plan_consume_item("Medkit")
    # # # mish.plan_trade(wither, money=4)
    # # ryo.set_dev_plan("Armed Combat I", "Armed Combat II", "Air II")
    # ryo.plan_attune(Element.AIR, Element.FIRE)
    # # # # ryo.plan_consume_item("Shrooms")
    # ryo.plan_attack(tempel)
    # # # # # # ryo.plan_shop("Oxygen Mask", "Shrooms", "Camo Cloak", "Booby Trap")
    # # # # # # ryo.plan_trade(para, item_names=["Gas Mask"])
    # # # # # tempel.set_dev_plan("Speed (Geo) I", "Willpower I", "Willpower II", "Willpower III", "Reinforced Will", "Cauterization", "Hell Fire", "Rune Crafting I", "Rune Crafting II")
    tempel.plan_attune(Element.AIR, Element.FIRE, Element.FIRE, Element.FIRE)
    # # # tempel.plan_consume_item("Fire Potion")
    # # # # tempel.plan_item_target("Mud Potion", girl)
    tempel.plan_attack(axe)
    # # # tempel.plan_trade(hotmonkey, money=7)
    # # wither.set_dev_plan("Quiet Attune")
    wither.plan_attune(Element.AIR, Element.AIR, Element.AIR, Element.ANTI)
    wither.plan_attack(girl)
    # wither.plan_consume_item("Poison Gas")
    # # # # wither.plan_shop("Workbench", "Paperwork")
    # # # # wither.plan_trade(star, item_names=["Workbench", "Paperwork"])
    # # # # wither.plan_trade(mish, money=2)
    # # wither.plan_train()
    # wither.plan_trade(hotmonkey, money=2)

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

    # GAME.save("Y25")


# git update-index --assume-unchanged main.py
# git update-index --no-assume-unchanged main.py
