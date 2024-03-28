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
                    items=item_pins, money=3, willpower=willpower, bounty=1,
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
    # Bothersome/Golden Rule
    create_player("23Starman",
                  ["Resurrection"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Stealth Resurrection", "Mental Fortification I"])
    # Blueballs/Exhibitionist
    create_player("Armstrong",
                  ["Warp", "Quiet Attune"],
                  temperament=Temperament.SCHOLASTIC,
                  dev_goals=["Air I", "Speed (Geo) I"])
    # Machismo/Instant Gratification
    create_player("anemone",
                  ["Copycat", "Awareness III"],
                  temperament=Temperament.LUCRATIVE,
                  dev_goals=["Circuit I", "Martial Arts I", "Counter Intelligence I", "Willpower I"])
    # Miasma/Stifle/Usury
    # Nothing to Hide/Cockroach
    create_player("Axeorthedark",
                  ["Stifle I", "Legacy Magic", "Bolthole"],
                  temperament=Temperament.PATIENT,
                  dev_goals=["Profiling", "Sabotage", "Know Thy Enemy"])
    # Nerd/Pacifist
    create_player("BlackLemonAde",
                  ["Envy IV"],
                  temperament=Temperament.PATIENT,
                  dev_goals=[])
    # No Escape/Bodyguard (Lord of Chromius)
    create_player("DarkPiplumon",
                  ["Copycat", "Ambush Tactics I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Awareness III", "Willpower Detection"])
    # Incandescence/Infinite Mana
    create_player("Dragonlord7",
                  ["Awareness I", "Crafting II"],
                  temperament=Temperament.INNOVATIVE,
                  dev_goals=["Crafting III", "Willpower II", "Willpower III"])
    # Paparazzi/Pre-K
    create_player("hotmonkey1",
                  ["Circuit III", "Water II"],
                  temperament=Temperament.SCHOLASTIC,
                  dev_goals=["Water III", "Air I", "Circuit IV", "Mist", "Earth I", "Circuit V", "Earth II", "Circuit VI"])
    # Statue Garden/Saint
    create_player("Lord of Chromius",
                  ["Circuit III", "Earth I", "Fire I"],
                  partial_dev={"Earth II": 5},
                  temperament=Temperament.SCHOLASTIC,
                  dev_goals=["Earth II", "Fast Attune I", "Fast Attune II", "Petrification I", "Lava"])
    # Bureaucracy/Conductor/Paperwork
    # Time Warp/Sycophant
    create_player("Megaolix",
                  ["Bureaucracy I", "Legacy Magic", "Enhanced Senses"],
                  partial_dev={"Danger Precognition": 5},
                  temperament=Temperament.PARANOIAC,
                  dev_goals=["Danger Precognition", "Willpower II", "Willpower III", "Reinforced Will"])
    # Revolution/Serial Killer (Dragonlord7, RyoAtemi, Tarro)
    create_player("NTKV",
                  ["Water III"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Circuit II", "Circuit III", "Rune Crafting I", "Runic Tattoos"])
    # Befoulment/Rapier/Zweihander
    # Silent but Deadly/Grand Heist
    create_player("Paradosi",
                  ["Befoulment I", "Legacy Magic",
                      "Armed Combat I", "Armored Combat"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=[])
    # Erode/Enfleshed/Rapier
    # Regressive Taxation/Just Browsing
    create_player("RyoAtemi",
                  ["Erode III", "Legacy Magic"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Circuit I", "Earth I", "Circuit II", "Earth II", "Circuit III", "Earth III"])
    # Hypochondria/Assassin: (Witherbrine26)
    create_player("Seventeen",
                  ["Fire I", "Water I", "Toxin", "Air I", "Mist", "Circuit III"],
                  temperament=Temperament.HOT_BLOODED,
                  conditions=[Condition.RINGER],
                  dev_goals=["Ash"])
    # Augur/Migraine/Yoga
    # Bully/Bureaucrat
    create_player("Swift-Sama",
                  ["Legacy Magic", "Migraine II", "Martial Arts I"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Migraine III", "Martial Arts II", "Armored Combat", "Forged in Fire", "Armed Combat I"])
    # Ebb/Journey/Parade
    # Spy Agency/Justice
    create_player("Tarro",
                  ["Parade II", "Legacy Magic", "Willpower I"],
                  temperament=Temperament.INTUITIVE,
                  dev_goals=["Body Reinforcement I", "Speed (Hydro) I", "Rapid Regen I", "Willpower II", "Rapid Regen II"])
    # Underdog/Contractor
    create_player("Teyao",
                  ["Paperwork I", "Paperwork II", "Combat Medicine",
                      "Circuit II", "Earth I", "Water I"],
                  temperament=Temperament.ALTRUISTIC,
                  partial_dev={"Paperwork III": 5},
                  conditions=[Condition.RINGER],
                  dev_goals=["Paperwork III"])
    # Class Clown/Predator
    create_player("Touch Dom",
                  ["Fire I", "Cauterization", "Ambush Tactics I"],
                  temperament=Temperament.HOT_BLOODED,
                  dev_goals=["Circuit II", "Fire II", "Circuit III", "Water I", "Toxin", "Martial Arts I"])
    # Meathead/Robot Army
    create_player("Witherbrine26",
                  ["Light", "Circuit II", "Magical Healing (Geo)"],
                  partial_dev={"Combat Regeneration (Geo)": 5},
                  temperament=Temperament.ALTRUISTIC,
                  dev_goals=["Combat Regeneration (Geo)", "Kaleidoscope", "Water I", "Water II"])
    # Hoarder/Money Bags
    create_player("Zeal Iskander",
                  ["Awareness II", "Attunement Detection", "Willpower Detection",
                      "Aeromancy Intuition", "Market Connections II"],
                  temperament=Temperament.PRIVILEGED,
                  dev_goals=["Bolthole", "Profiling", "Awareness III"])

    summary()


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
    # init()
    load("Y17", turn=10, night=False)

    star = GAME.get_player("23Starman")
    arm = GAME.get_player("Armstrong")
    ane = GAME.get_player("anemone")
    axe = GAME.get_player("Axeorthedark")
    bla = GAME.get_player("BlackLemonAde")
    dark = GAME.get_player("DarkPiplumon")
    drag = GAME.get_player("Dragonlord7")
    hot = GAME.get_player("hotmonkey1")
    lord = GAME.get_player("Lord of Chromius")
    mega = GAME.get_player("Megaolix")
    ntkv = GAME.get_player("NTKV")
    para = GAME.get_player("Paradosi")
    ryo = GAME.get_player("RyoAtemi")
    seven = GAME.get_player("Seventeen")
    swift = GAME.get_player("Swift-Sama")
    tarro = GAME.get_player("Tarro")
    teyao = GAME.get_player("Teyao")
    touch = GAME.get_player("Touch Dom")
    wither = GAME.get_player("Witherbrine26")
    zeal = GAME.get_player("Zeal Iskander")

    GAME.advance()
    # summary(detailed=True)
    # exit(0)

    # # 23Starman: Golden Rule [Darkpiplumon, Paradosi, Touch Dom]
    # star.plan_hydro("Illusions I")
    star.plan_hydro("Resurrection", contingency=True)
    star.plan_bunker()
    # star.plan_shop("Liquid Memories", "Cheat Sheet")
    # star.plan_illusion(star, Wander(None, star))
    # # # # # # # # # # # # star.plan_trade(para, money=2, action_condition=(para, Attack, star, False))
    # # # # # # # # star.set_dev_plan("Illusions I", "Rapid Regen I", "Mental Fortification I")
    # # # # # # # # # # # # # # # # # # # # BlackLemonAde: Pacifist
    # # # # bla.plan_consume_item("Paperwork")
    bla.plan_attune(Element.EARTH)
    bla.plan_attack(hot)
    # # bla.plan_trade(dark, item_names=['Paperwork'])
    # # # # # # # # # # # bla.set_dev_plan("Martial Arts I", "Armed Combat I", "Sniping", "Circuit II", "Antimagic (Geo)")
    # # # # # # # # # # # # # # # # # # #
    # # # # # # # # # # # # # # # # # # # Darkpiplumon: No Escape 0/1
    dark.plan_consume_item("Paperwork")
    dark.plan_hydro("Enhanced Senses")
    dark.plan_hydro("Body Reinforcement I", will=[1, 0], contingency=False)
    dark.plan_attune(Element.FIRE, Element.AIR, Element.ANTI, Element.WATER)
    dark.plan_attack(teyao)
    # # # # dark.plan_trade(drag, money=2, item_name_condition=(drag, 0, ['Leather Armor']))
    dark.plan_spy(mega, star)
    # # # # # # # # # # # # # dark.plan_shop("Paperwork", "Paperwork", "Paperwork", "Paperwork", "Shrooms", "Shrooms")
    # # # # # # # # # # # # dark.plan_trade(drag, money=1, item_name_condition=(drag, 0, ['Soft']))
    # # dark.set_dev_plan("Air I", "Circuit IV", "Warp")
    # # # # # # # # # # # # # # # # # # #
    # # # # # # # # # # # # # # # # # # # # hotmonkey1: Pre-K 1/1 Night 6
    # # # # # # # # # # hot.plan_consume_item("Paperwork")
    hot.plan_attune(Element.WATER, Element.WATER, Element.WATER, Element.ANTI)
    hot.plan_attack(star)
    # # hot.plan_trade(ryo, money=1)
    # # hot.plan_trade(para, item_names=['Force Projection'])
    # # # hot.set_dev_plan("Martial Arts II", "Martial Arts III")
    # # # # # # # # # # # # # # # # # # #
    # # # # # # # # # # # # # # # # # # # # NTKV: Serial Killer Dragonlord7, RyoAtemi, Tarro (2/3) []
    ntkv.plan_attune(Element.WATER, Element.WATER, Element.WATER, Element.FIRE)
    # # # # # # # # # # # # # # ntkv.plan_consume_item("Shrooms")
    ntkv.plan_attack(ryo)
    # # ntkv.set_dev_plan("Toxin", "Antimagic (Geo)")
    # # # # # # # # # # # # # # # ntkv.plan_shop("Lizard Tail", "Shrooms")
    # # # # # # # # # # # # # # # # # # #
    # # # # # # # # # # # # # # # # # # # # Paradosi: Grand Heist 1/1 Night 8
    para.plan_consume_item("Venom")
    para.plan_attack(hot)
    para.plan_spy(mega, teyao)
    # # # # # para.plan_shop("Lizard Tail", "Lizard Tail", "Paperwork", "Paperwork", "Paperwork", "Paperwork", "Paperwork", "Paperwork", "Paperwork")
    # # # para.plan_trade(ryo, money=1, item_names=['Leather Armor'])
    # para.plan_trade(hot, item_names=["Leather Armor"])
    # # para.plan_trade(ryo, money=1)
    # para.plan_class()
    # # # # # # # # para.plan_attack(arm)
    # # # # # # # # para.plan_spy(star)
    # # # # # # # # # # # para.plan_shop("Sword", "Poison Gas", "Poison Gas", "Paperwork", "Paperwork", "Paperwork", "Paperwork", "Booby Trap")
    # # # # # # # # # # # para.plan_trade(ryo, item_names=['Paperwork'])
    # # # # # # # # # # # para.plan_trade(hot, item_names=['Paperwork'])
    # # para.set_dev_plan("Counter Intelligence I", "Sniping")
    # # # # # # # # # # # # # # # # # # #
    # # # # # # # # # # # # # # # # # # # # RyoAtemi: Reverse Taxation 0/1
    ryo.plan_attune(Element.EARTH, Element.EARTH, Element.EARTH)
    ryo.plan_target("Erode III", ntkv, teyao, bla)
    # # # # # # # # # ryo.plan_consume_item("Paperwork")
    ryo.plan_attack(star)
    # ryo.plan_shop("Liquid memories", "paperwork", "poison gas")
    # ryo.plan_trade(para, item_names=['Liquid Memories'])
    # ryo.plan_trade(dark, item_names=['Paperwork'])
    # # # # # # # # # # ryo.plan_trade(ntkv, item_names=['Singing Stone'])
    # # # # # # # # # # # # # # # # # ryo.set_dev_plan("Circuit I", "Earth I", "Earth II", "Circuit II", "Earth III", "Circuit III")
    # # # # # # # # # # # # # # # # # # #
    # # # # # # # # # # # # # # # # # # # # Teyao: Contractor 1/5 [NTKV]
    teyao.plan_hydro("Enhanced Senses")
    teyao.plan_hydro("Speed (Hydro) I", contingency=True)
    teyao.plan_hydro("Speed (Hydro) II", contingency=True)
    teyao.plan_attune(Element.AIR, Element.EARTH, Element.AIR)
    teyao.plan_bunker()
    # # teyao.plan_heal(ntkv)
    # # # # teyao.plan_trade(drag, money=3, item_name_condition=(drag, 0, ['Medkit']))
    # # # # # # # # # # # # # # # # teyao.plan_bounty(ntkv, 2)
    # # # # # # teyao.set_dev_plan("Reinforced Will", "Speed (Hydro) II")
    # # # # # # # # # # # # # # # # # # #
    # # # # # # # # # # # # # # # # # # # # Touch Class Clown 0/2
    # # # touch.plan_consume_item("Paperwork")
    touch.plan_attune(Element.FIRE, Element.ANTI)
    touch.plan_attack(star)
    # # # # # touch.plan_trade(para, money=3)
    # # # # # # # # # # touch.plan_trade(wither, money=1, action_condition=(wither, Heal, touch))
    # # touch.set_dev_plan("Ambush Tactics II", "Circuit III", "Water I", "Fire II")
    # # # # # # # # # # # # # # # #

    was_alive = [p for p in GAME.players.values() if not p.is_dead()]
    Action.run_turn(GAME)
    for p in was_alive:
        print(f"{p.name} Report{os.linesep}")
        print(p.get_report())
        print()

    print(get_main_report().generate_report(GAME))
    # # # # # # #
    summary(detailed=True)

    # GAME.save("Y17")


# git update-index --assume-unchanged main.py
# git update-index --no-assume-unchanged main.py
