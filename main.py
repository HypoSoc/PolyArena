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
    create_player("A Nice Girl",
                  ["Martial Arts III", "Armed Combat I", "Sniping", "Armed Combat II"],
                  dev_goals=["Circuit I", "Air I", "Speed (Geo) I"],
                  temperament=Temperament.PRIVILEGED,
                  items=['Lizard Tail'],
                  conditions=[Condition.YEAR_1])

    create_player("Amonclone4321",
                  ["Martial Arts III", "Counter Ambush Tactics", "Ambush Tactics II", "Armed Combat I", "Awareness II"],
                  dev_goals=["Awareness III", "Panopticon"],
                  temperament=Temperament.BLOODTHIRSTY,
                  items=['Lizard Tail'],
                  conditions=[Condition.YEAR_3, Condition.RINGER])

    create_player("Anemone",
                  ["Circuit II", "Light", "Water I", "Combat Regeneration (Geo)", "Warp I"],
                  dev_goals=[],
                  temperament=Temperament.ALTRUISTIC,
                  items=['Lizard Tail'],
                  conditions=[Condition.YEAR_3, Condition.RINGER])

    create_player("BlackLemonAde",
                  ["Magical Healing (Hydro)", "Illusions I", "Combat Regeneration (Hydro)"],
                  dev_goals=["Rapid Regen I", "Willpower III", "Rapid Regen II", "Reinforced Will"],
                  temperament=Temperament.ALTRUISTIC,
                  items=['Leather Armor', 'Venom'],
                  conditions=[Condition.YEAR_2])

    create_player("Darklight140",
                  ["Awareness I", "Body Reinforcement III", "Mental Fortification I", "Quiet Casting"],
                  dev_goals=["Profiling", "Counter Intelligence I", "Rapid Regen I"],
                  temperament=Temperament.PSYCHO,
                  items=['Network Spike', 'Venom'],
                  conditions=[Condition.YEAR_3, Condition.RINGER])

    create_player("Darkpiplumon",
                  ["Willpower III", "Illusions III"],
                  dev_goals=["Rapid Regen I", "Autopilot", "Willpower IV"],
                  temperament=Temperament.SCHOLASTIC,
                  items=['Fire Potion', 'Fire Potion', 'Frost Potion'],
                  conditions=[Condition.YEAR_1])

    create_player("Dragonlord7",
                  ["Circuit II", "Water I", "Fire I", "Toxin"],
                  dev_goals=["Water II", "Circuit III", "Water III", "Circuit IV"],
                  temperament=Temperament.BLOODTHIRSTY,
                  items=['Network Spike', 'Mud Potion'],
                  conditions=[Condition.YEAR_1])

    create_player("hotmonkey1",
                  ["Fire III", "Circuit III", "Attunement Detection", "Ambush Tactics I"],
                  dev_goals=["Cauterization", "Hell Fire"],
                  temperament=Temperament.PRIVILEGED,
                  items=['Earth Potion', 'Soft'],
                  conditions=[Condition.YEAR_3, Condition.RINGER])

    create_player("Jaguar2234",
                  ["Awareness I", "Circuit III", "Fire II"],
                  partial_dev={"Fire III": 5},
                  dev_goals=["Fire III"],
                  temperament=Temperament.BLOODTHIRSTY,
                  items=['Pyrite Potion', 'Medkit'],
                  conditions=[Condition.YEAR_2])

    create_player("Lord of Chromius",
                  ["Will Armor II", "Body Reinforcement I", "Willpower III", "Rapid Regen I"],
                  dev_goals=["Body Reinforcement II"],
                  temperament=Temperament.SCHOLASTIC,
                  items=['Pyrite Potion', 'Earth Potion', 'Venom'],
                  conditions=[Condition.YEAR_2])

    create_player("mishtazespy",
                  ["Circuit III", "Fire III", "Awareness I"],
                  dev_goals=["Attunement Detection", "Ambush Tactics I"],
                  temperament=Temperament.PRIVILEGED,
                  items=['Medkit', 'Fire Potion'],
                  conditions=[Condition.YEAR_2])

    create_player("Nightfire",
                  ["Circuit II", "Earth III", "Rune Crafting I"],
                  partial_dev={"Runic Tattoos": 5},
                  dev_goals=["Runic Tattoos", "Circuit III", "Rune Crafting II", "Air I", "Fast Attune I"],
                  temperament=Temperament.PRIVILEGED,
                  items=['Earth Potion', 'Leather Armor'],
                  conditions=[Condition.YEAR_2])

    # Chalk/Edifice/Horn
    create_player("NinetyNineLies",
                  ["Horn IV", "Legacy Magic"],
                  partial_dev={"Horn V": 5},
                  dev_goals=["Horn V", "Awareness I"],
                  temperament=Temperament.STUBBORN,
                  items=['Lizard Tail'],
                  conditions=[Condition.YEAR_2])

    create_player("Paradosi",
                  ["Mystic Penetration", "Counter Ambush Tactics"],
                  partial_dev={"Sniping (Hydro)": 5},
                  dev_goals=["Sniping (Hydro)", "Martial Arts I", "Armed Combat I"],
                  temperament=Temperament.PSYCHO,
                  items=['Earth Potion', 'Venom', 'Earth Potion'],
                  conditions=[Condition.YEAR_3, Condition.RINGER])

    create_player("RyoAtemi",
                  ["Circuit II", "Antimagic (Geo)", "Martial Arts II"],
                  dev_goals=["Air I", "Martial Arts III", "Fast Attune I", "Fast Attune II", "Armored Combat", "Armed Combat I", "Awareness I", "Awareness II"],
                  temperament=Temperament.SCHOLASTIC,
                  items=['Lizard Tail'],
                  conditions=[Condition.YEAR_1])

    create_player("Seventeen",
                  ["Ambush Tactics I", "Martial Arts III", "Armed Combat II"],
                  dev_goals=["Sniping", "Awareness II", "Armor Break", "Ambush Tactics II", "Counter Ambush Tactics"],
                  temperament=Temperament.BLOODTHIRSTY,
                  items=['Lizard Tail'],
                  conditions=[Condition.YEAR_2])

    create_player("Swift-Sama",
                  ["Circuit II", "Fire II"],
                  partial_dev={"Fire III": 5},
                  dev_goals=["Fire III", "Circuit III", "Air I", "Circuit IV", "Ash", "Martial Arts I", "Armed Combat I", "Armed Combat II", "Awareness I"],
                  temperament=Temperament.BLOODTHIRSTY,
                  items=['Earth Potion', 'Medkit'],
                  conditions=[Condition.YEAR_1])

    create_player("Tempeljaeger",
                  ["Crafting III", "Illusions III", "Willpower III"],
                  dev_goals=["Willpower IV", "Soul Strike", "Willpower V"],
                  temperament=Temperament.INNOVATIVE,
                  items=['Venom', 'Venom', 'Fire Potion'],
                  conditions=[Condition.YEAR_2, Condition.RINGER])

    create_player("Teyao",
                  ["Edifice II", "Illusions III", "Willpower III"],
                  dev_goals=["Edifice III", "Enhanced Senses", "Danger Precognition", "Willpower IV", "Willpower V"],
                  temperament=Temperament.SCHOLASTIC,
                  items=['Soft', 'Fire Potion'],
                  conditions=[Condition.YEAR_1, Condition.RINGER])

    # Envy/Enfleshed/Augur
    create_player("Witherbrine26",
                  ["Envy II", "Legacy Magic", "Awareness I", "Martial Arts I"],
                  dev_goals=["Martial Arts II", "Armed Combat I", "Envy III"],
                  temperament=Temperament.INTUITIVE,
                  items=["Face Mask", "Earth Potion"],
                  conditions=[Condition.YEAR_1])

    create_player("Zeal Iskander",
                  ["Earth III", "Circuit II"],
                  dev_goals=["Circuit III", "Martial Arts I", "Martial Arts II", "Martial Arts III"],
                  temperament=Temperament.PRIVILEGED,
                  items=["Face Mask", "Earth Potion"],
                  conditions=[Condition.YEAR_1])

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

    load("Y27")
    #

    girl = GAME.get_player("A Nice Girl")
    amon = GAME.get_player("Amonclone4321")
    anemone = GAME.get_player("Anemone")
    bla = GAME.get_player("BlackLemonAde")
    darklight = GAME.get_player("Darklight140")
    darkpip = GAME.get_player("Darkpiplumon")
    dragon = GAME.get_player("Dragonlord7")
    hot = GAME.get_player("hotmonkey1")
    jaguar = GAME.get_player("Jaguar2234")
    lord = GAME.get_player("Lord of Chromius")
    mish = GAME.get_player("mishtazespy")
    night = GAME.get_player("Nightfire")
    nine = GAME.get_player("NinetyNineLies")
    para = GAME.get_player("Paradosi")
    ryo = GAME.get_player("RyoAtemi")
    seventeen = GAME.get_player("Seventeen")
    swift = GAME.get_player("Swift-Sama")
    tempel = GAME.get_player("Tempeljaeger")
    teyao = GAME.get_player("Teyao")
    wither = GAME.get_player("Witherbrine26")
    zeal = GAME.get_player("Zeal Iskander")

    GAME.advance()

    girl.plan_consume_item("Medkit")
    girl.plan_heal(girl)
    # # girl.plan_shop("Lizard Tail", "Medkit")
    # # anemone.set_dev_plan("Antimagic (Geo)")
    # # anemone.plan_attune(Element.WATER, Element.LIGHT, Element.WARP)
    # # # # anemone.plan_heal(anemone)
    # # anemone.plan_target("Warp I", hot)
    # # anemone.plan_attack(hot)
    # # # anemone.plan_shop("Gas Mask", "Poison Gas", "Poison Gas", "Soft", "Soft", "Lizard Tail")
    # # # anemone.plan_trade(wither, item_names=["Lizard Tail", "Gas Mask", "Poison Gas", "Poison Gas"])
    # # # # # # # # # # #
    # # # # # # bla.set_dev_plan("Rapid Regen II", "Willpower III", "Reinforced Will")
    # # bla.plan_hydro("Magical Healing (Hydro)")
    # # # # # bla.plan_hydro("Body Reinforcement I", will=[0,1])
    # # # # # # bla.plan_consume_item("Shrooms")
    # # # # # # bla.plan_hydro("Illusions I")
    # # # # # # bla.plan_illusion(bla, Bunker(None, bla, False))
    bla.plan_hydro("Combat Regeneration (Hydro)", contingency=True)
    bla.plan_train()
    # # # # # bla.plan_doctor()
    # # # # # # # # # # #
    # # # # # # # # # # # darklight.set_dev_plan("Rapid Regen I", "Rapid Regen II")
    # # # # # # darklight.plan_consume_item("Fire Potion")
    # darklight.plan_hydro("Body Reinforcement I", will=[0,1], contingency=False)
    # # darklight.plan_hydro("Body Reinforcement II", will=[0,0], contingency=True)
    darklight.plan_hydro("Body Reinforcement III", will=[0,3], contingency=False)
    darklight.plan_hydro("Mental Fortification I")
    darklight.plan_attack(night)
    # # # darklight.plan_doctor()
    # # darklight.plan_bunker()
    # # # # # darklight.plan_trade(seventeen, item_names=["Network Spike"])
    # # # # # # # # # # #
    # # # # # # # # # darkpip.set_dev_plan("Autopilot", "Willpower IV", "Willpower V")
    # # # # # # # # # # # darkpip.plan_hydro("Illusions I")
    # # # # # # # # # # hot.set_dev_plan("Willpower Detection", "Cauterization", "Hell Fire")
    hot.plan_attune(Element.FIRE, Element.FIRE, Element.FIRE)
    # # # # # # # # hot.plan_face_mask(teyao)
    # # # # # hot.plan_consume_item("Earth Potion")
    hot.plan_attack(swift)
    # # # # # # # hot.plan_bunker(bonus=True)
    # # hot.plan_trade(zeal, item_names=["Synthetic Weave"])
    # hot.plan_trade(night, money=2)
    # # # # # # # # # # #
    # lord.set_dev_plan("Enhanced Senses", "Martial Arts I", "Will Blades", "Mystic Penetration", "Sniping (Hydro)")
    # # lord.plan_consume_item("Venom")
    lord.plan_hydro("Will Armor II", contingency=True)
    # # # # # # # lord.plan_hydro("Body Reinforcement I", will=[0,1], contingency=True)
    lord.plan_hydro("Body Reinforcement II", will=[0,3], contingency=True)
    # # # # # # lord.plan_consume_item("Medkit")
    lord.plan_bunker()
    # lord.plan_doctor()
    # # # # # # # lord.plan_shop("Lizard Tail", "Medkit")
    # # # # # # # # # # #
    # # # # # # # # # # #
    # # # # night.set_dev_plan("Antimagic (Geo)", "Antimagic (Hydro)")
    night.plan_attune(Element.EARTH, Element.EARTH)
    # # # # # night.plan_doctor()
    night.plan_bunker(bonus=True)
    # # # # night.plan_consume_item("Shrooms")
    night.plan_attack(bla, lord, darklight)
    # # # # # # # night.plan_tattoo(night, "Earth III")
    # # # # # # # # # night.plan_shop("Oxygen Mask", "Sword", "Shrooms")
    # night.plan_trade(hot, item_names=["Leather Armor"])
    # night.plan_trade(zeal, item_names=["Healing Tank"])
    # # # # # # # # # # #
    # # # seventeen.set_dev_plan("Ambush Tactics II")
    # # # # # seventeen.plan_shop("Ablative Ossification")
    # seventeen.plan_attack(hot)
    # # # # # # # # # # #
    # # # # swift.plan_consume_item("Medkit")
    # # swift.set_dev_plan("Air I", "Antimagic (Hydro)", "Ash")
    swift.plan_attune(Element.FIRE, Element.FIRE, Element.FIRE)
    # # swift.plan_get_tattoo(night)
    # swift.plan_shop("Laser Sword", "Shrooms")
    # # # # # # # # # # #
    # # # # # # # teyao.set_dev_plan("Edifice IV", "Edifice V", "Crafting I", "Willpower IV")
    # # # # # # # teyao.plan_hydro("Illusions I")
    # teyao.plan_hydro("Illusions III", targets=[girl, teyao, seventeen])
    # # # # teyao.plan_illusion(teyao, Bunker(None, teyao, False), ability="Circuit III")
    # teyao.plan_class()
    # # # # # # # # # # #
    # # # # # # wither.set_dev_plan("Circuit I", "Water I", "Circuit II", "Antimagic (Geo)")
    # # # wither.plan_attune(Element.WATER)
    # # # wither.plan_consume_item("Earth Potion")
    # # # # wither.plan_attack(teyao)
    # # # # wither.plan_spy(night)
    # # # # wither.plan_trade(anemone, money=4)
    # # # wither.plan_doctor()
    # # # # # # # # # # #
    zeal.set_dev_plan("Petrification I")
    # zeal.plan_attune(Element.EARTH, Element.EARTH, Element.EARTH)
    # zeal.plan_attack(swift, darklight, seventeen)
    zeal.plan_bunker(bonus=True)
    zeal.plan_train()
    # # # zeal.plan_shop("Shrooms", "Healing Tank", "Synthetic Weave")
    # # # zeal.plan_trade(night, item_names=["Shrooms"])
    # # zeal.plan_attack(wither, teyao, anemone)
    # zeal.plan_trade(hot, item_names=["Sword"], item_name_condition=(hot, 0, ["Synthetic Weave"]))
    # zeal.plan_trade(night, money=3, item_names=["Leather Armor", "Healing Tank"], item_name_condition=(hot, 0, ["Synthetic Weave"]))

    was_alive = [p for p in GAME.players.values() if not p.is_dead()]
    Action.run_turn(GAME)
    for p in was_alive:
        print(f"{p.name} Report{os.linesep}")
        print(p.get_report())
        print()

    print(get_main_report().generate_report(GAME))
    # # # # # # #
    summary(detailed=True)

    # GAME.save("Y27")


# git update-index --assume-unchanged main.py
# git update-index --no-assume-unchanged main.py
