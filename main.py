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
GAME.seed = 88717

combat.DEBUG = False

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


def load(file_prefix: str=None, turn: int = None, night: bool = None, data=None):
    if data is None:
        if turn is None or night is None:
            f = open(f"save/{file_prefix}/current.json", 'r')
        else:
            f = open(
                f"save/{file_prefix}/{turn}{'n' if night else 'd'}.json", 'r')
        data = json.load(f)
        f.close()
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

def king_choice(action: str):
    return ['class', 'doctor', 'train', 'bunker', 'shop', 'wander', 'none'].index(action.lower())

class reversor:
    def __init__(self, obj):
        self.obj = obj

    def __eq__(self, other):
        return other.obj == self.obj

    def __lt__(self, other):
        return other.obj < self.obj

# displays a leaderboard of players based on their total progress. 
# players have a # position, ties noted as being in the same position, names are sorted alphabetically in case of ties.
# the leaderboard only displays player names. Players that are dead or in hiding are not displayed.
def leaderboard(total_dev=False, leaderboard_academics=False):
    players = [player for player in GAME.players.values() if not player.is_dead() and player.conditions.count(Condition.HIDING) == 0]
    if leaderboard_academics:
        players.sort(key=lambda x: (reversor(x.academics), x.name))
    else:
        players.sort(key=lambda x: (reversor(x.get_total_dev()), x.name))
    currentposition = 1
    print(f'[font="courier new"][center][h2]Leaderboard[/h2]', end="")
    for i, player in enumerate(players):
        position = i + 1
        pos_changed = player.get_total_dev() < players[i-1].get_total_dev() if not leaderboard_academics else player.academics < players[i-1].academics
        if i == 0 or pos_changed:
            currentposition = position
            print(f"\n#{currentposition} {'(' + str(player.academics if leaderboard_academics else player.get_total_dev()) + ')' if total_dev else ''}: {player.name}", end="")
        else:
            print(f", {player.name}", end="")
        if i == 0:
            # crown emoji
            print(" \U0001F451", end="")
    print(f'[/center][/font]\n')

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
                if player.tattoo:
                    out += f"Tattoo: {get_item(player.tattoo).name}\n"
                dev_goals = [get_ability(ability).name for ability in player.dev_plan]
                if dev_goals:
                    out += f"Dev Goals: {', '.join(dev_goals)}\n"
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

def report(player_reports=True, main_report=True, leaderboard_report=False, leaderboard_total_devs=True, leaderboard_academics=False, summary_report=True, summary_detailed=True): 
    if player_reports: 
        data = ""
        for p in GAME.was_alive:
            data += os.linesep
            data += f"{p.name} Report{os.linesep}{os.linesep}"
            data += p.get_report()
            data += os.linesep
        print(data)
        import pyperclip
        pyperclip.copy(data)
    if main_report:
        print(get_main_report().generate_report(GAME))
    if leaderboard_report:
        leaderboard(total_dev=leaderboard_total_devs, leaderboard_academics=leaderboard_academics)
    if summary_report:
        summary(detailed=summary_detailed)

def clear():
    reset_action_handler()
    load(data=GAME.serialize())
    get_main_report().reset()
    get_combat_handler().reset()
    GAME.advance()

### ===================== ###

def Anemone():
    return GAME.get_player("Anemone")
def Bedna():
    return GAME.get_player("Bedna")
def BlackLemonAde():
    return GAME.get_player("BlackLemonAde")
def Coledon():
    return GAME.get_player("Coledon")
def DarkLight():
    return GAME.get_player("DarkLight")
def Darkpiplumon():
    return GAME.get_player("Darkpiplumon")
def DragonLord():
    return GAME.get_player("DragonLord")
def Drasky():
    return GAME.get_player("Drasky")
def Hotmonkey():
    return GAME.get_player("Hotmonkey")
def HypoSoc():
    return GAME.get_player("HypoSoc")
def LordOfChromius():
    return GAME.get_player("Lord Of Chromius")
def Megaolix():
    return GAME.get_player("Megaolix")
def NinetyNineLies():
    return GAME.get_player("NinetyNineLies")
def Paradosi():
    return GAME.get_player("Paradosi")
def PocketRikimaru():
    return GAME.get_player("PocketRikimaru")
def RyoAtemi():
    return GAME.get_player("RyoAtemi")
def Seventeen():
    return GAME.get_player("Seventeen")
def SwiftSama():
    return GAME.get_player("Swift-Sama")
def TempelJaeger():
    return GAME.get_player("TempelJaeger")
def Teyao():
    return GAME.get_player("Teyao")
def Witherbrine():
    return GAME.get_player("Witherbrine")

def load_players():
    clear()
    return Anemone(), Bedna(), BlackLemonAde(), Coledon(), DarkLight(), Darkpiplumon(), DragonLord(), Drasky(), Hotmonkey(), HypoSoc(), LordOfChromius(), Megaolix(), NinetyNineLies(), Paradosi(), PocketRikimaru(), RyoAtemi(), Seventeen(), SwiftSama(), TempelJaeger(), Teyao(), Witherbrine()

def init():
    create_player("Anemone",
                  abilities=['Warp', "Styx"],
                  temperament=Temperament.PARANOIAC)
    create_player("Bedna",
                  abilities=['Awareness I', 'Awareness II', 'Sabotage', 'Fall'],
                  dev_goals=['Aeromancy Intuition', 'Profiling'],
                  temperament=Temperament.PATIENT)
    create_player("BlackLemonAde",
                  abilities=['Chaos', 'Unnatural Intuition', 'Body Reinforcement I'],
                  temperament=Temperament.PATIENT)
    create_player("Coledon",
                  abilities=['Circuit I', 'Circuit II', 'Quiet Attune', 'Three'],
                  temperament=Temperament.SCHOLASTIC,
                  dev_goals=['Air I', 'Air II', 'Speed (Geo) I', 'Speed (Geo) II'])
    create_player("DarkLight",
                  abilities=['Combat Regeneration (Hydro)'],
                  dev_goals=['Willpower II', 'Awareness I', 'Awareness II', 'Know Thy Enemy', 'Psy Ops'],
                  temperament=Temperament.ALTRUISTIC)
    create_player("Darkpiplumon", 
                  abilities=['Gold', 'Chameleon'], 
                  dev_goals=['Earth I'], 
                  temperament=Temperament.PATIENT)   
    create_player("DragonLord",
                  abilities=['Savior', 'Awareness I', 'Martial Arts III'],
                  temperament=Temperament.BLOODTHIRSTY)
    create_player("Drasky",
                  abilities=['Martial Arts II', 'Armed Combat I', 'Armed Combat II', 'Split', 'Armored Combat', 'Earth I'],
                  conditions=[Condition.RINGER],
                  temperament=Temperament.BLOODTHIRSTY)
    create_player("Hotmonkey",
                  abilities=['Awareness I', 'Willpower Detection', 'Aeromancy Intuition', 'Awareness II', 'Swap'],
                  dev_goals=['Attunement Detection', 'Bolthole', 'Awareness III', 'Know Thy Enemy', 'Psy Ops'],
                  temperament=Temperament.PATIENT)
    create_player("HypoSoc", 
                  abilities=['Circuit I', 'Circuit II', 'Fire I', 'Water I', 'Toxin'], 
                  dev_goals=['Circuit III', 'Antimagic (Aero)', 'Air I', 'Ash', 'Circuit IV'], 
                  temperament=Temperament.HOT_BLOODED)
    create_player("Lord Of Chromius",
                  abilities=['Circuit I', 'Earth I', 'Nuclear I', 'Legacy Magic', 'Awareness I'],
                  dev_goals=['Circuit II', 'Light', 'Speed (Geo) I', 'Nuclear II'],
                  temperament=Temperament.INTUITIVE)
    create_player("Megaolix", 
                  abilities=['Circuit I', 'Circuit II', 'Earth I', 'Water I', 'Mud'], 
                  dev_goals=['Circuit III', 'Air I', 'Dust', 'Mist', 'Speed (Geo) I'], 
                  temperament=Temperament.PATIENT)
    create_player("NinetyNineLies", 
                  abilities=['Willpower I', 'Enhanced Senses', 'Unnatural Intuition', 'Slip', 'Awareness I'],
                  temperament=Temperament.PATIENT)
    create_player("Paradosi",
                  abilities=['Willpower I', 'Mental Fortification I', 'Mental Fortification II', 'Arsonist'],
                  temperament=Temperament.PATIENT)
    create_player("PocketRikimaru",
                  abilities=['Gold', 'Mental Fortification I'],
                  dev_goals=['Martial Arts I', 'Martial Arts II', 'Martial Arts III', 'Armed Combat I', 'Armored Combat'],
                  temperament=Temperament.LUCRATIVE)  
    create_player("RyoAtemi", 
                  abilities=['Omniscience', 'Awareness I', 'Awareness II', 'Sabotage'], 
                  temperament=Temperament.PATIENT)
    create_player("Seventeen", 
                  abilities=['Recursion', 'Martial Arts III', 'Combat Medicine'], 
                  dev_goals=['Armed Combat I', 'Armed Combat II'],
                  temperament=Temperament.ALTRUISTIC)
    create_player("Swift-Sama",
                  abilities=['King', 'Circuit I', 'Water I', 'Magical Healing (Geo)'],
                  temperament=Temperament.ALTRUISTIC)
    create_player("TempelJaeger",
                  abilities=['Earth I', 'Willpower I', 'Mental Fortification I', 'Jackpot', 'X', 'Scapegoat I', 'Augur I'],
                  temperament=Temperament.PARANOIAC)
    create_player("Teyao", 
                  abilities=['Circuit I', 'Water I', 'Magical Healing (Geo)', 'Wealth'], 
                  dev_goals=['Water II'], 
                  temperament=Temperament.ALTRUISTIC)
    create_player("Witherbrine", 
                  abilities=['Void', 'Earth I', 'Earth II', 'Circuit I'], 
                  dev_goals=['Circuit II'], 
                  temperament=Temperament.PATIENT)

"""
Anemone:
Shop for a Workbench.

Bedna:
Train
Fall: Drasky.

BlackLemonAde:
Train
Body Reinforcement I: +1 surv
Unnatural Intuition (contingency)

Coledon:
Attack Megaolix.

DarkLight:
Teach Swift-Sama Willpower I
Combat Regeneration (Hydro) (contingency)

Darkpiplumon:
Attune to Gold
Train

DragonLord:
Attack RyoAtemi.

Drasky:
Shop for Leather Armor and Bokken.
Attune to Earth.

Hotmonkey:
Train

HypoSoc:
Attune to Water and Fire.
Attack Hotmonkey.

Lord Of Chromius:
Train
Attune to Earth.

Megaolix:
Train
Attune to Earth and Water.

NinetyNineLies:
Shop for a Sword.
Unnatural Intuition (contingency)

Paradosi:
Train

PocketRikimaru:
Train
Attune to Gold
Mental Fortification I

RyoAtemi:
Train

Seventeen:
Tattoo Rune Crafting II on self.

Swift-Sama:
Learn from DarkLight.
King: Train

TempelJaeger:
Learn from Teyao.
Attune to Earth

Teyao:
Teach TempelJaeger Water I
Attune to Water
Trade 1 credit to Anemone, Hotmonkey, Darkpiplumon

Witherbrine:
Train
Attune to Earth
"""
def turn_1():
    anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, hot, hypo, lord, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_shop('Workbench')
    anemone.set_dev_plan('Willpower I', 'Crafting I', 'Crafting II')

    bedna.plan_train()
    bedna.plan_target('Fall', drasky)
    bedna.set_dev_plan('Profiling', 'Aeromancy Intuition', 'Bolthole')
    
    black.plan_train()
    black.plan_hydro('Body Reinforcement I', [0, 1])
    black.plan_hydro('Unnatural Intuition', contingency=True)
    black.set_dev_plan('Body Reinforcement II', 'Rapid Regen I')

    cole.plan_attack(mega)

    darklight.plan_teach(swift, 'Willpower I')
    darklight.plan_hydro('Combat Regeneration (Hydro)', contingency=True)

    darkpip.plan_train()
    darkpip.plan_attune(Element.GOLD)
    darkpip.set_dev_plan('Earth I', 'Martial Arts I', 'Martial Arts II')

    dragon.plan_attack(ryo)
    dragon.set_dev_plan('Armored Combat', 'Circuit I', 'Fire I', 'Fire II', 'Circuit II', 'Air I', 'Ash', 'Circuit III')
   
    # bounced by Styx rule as they shopped for all of their credit.
    # drasky.plan_shop('Leather Armor', 'Bokken')
    # drasky.plan_attune(Element.EARTH)
    # drasky.set_dev_plan('Martial Arts III', 'Fire I', 'Circuit II', 'Antimagic (Geo)')

    hot.plan_train()
    
    hypo.plan_attack(hot)
    hypo.plan_attune(Element.WATER, Element.FIRE)

    lord.plan_train()
    lord.plan_attune(Element.EARTH)
    lord.set_dev_plan('Circuit II', 'Light', 'Kaleidoscope', 'Circuit III', 'Nuclear II')

    mega.plan_train()
    mega.plan_attune(Element.EARTH, Element.WATER)

    # bounced by Styx rule as they shopped for all of their credit.
    # ninety.plan_shop("Sword")
    # ninety.plan_hydro('Unnatural Intuition', contingency=True)
    # ninety.set_dev_plan('Willpower II', 'Will Armor I', 'Body Reinforcement I', 'Body Reinforcement II', 'Body Reinforcement III')

    para.plan_train()
    para.set_dev_plan('Body Reinforcement I', 'Body Reinforcement II', 'Body Reinforcement III')

    pocket.plan_train()
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')
    pocket.set_dev_plan('Martial Arts I', 'Martial Arts II', 'Martial Arts III', 'Armed Combat I', 'Armored Combat')

    ryo.plan_train()

    seven.plan_tattoo(seven, 'Rune Crafting II')

    swift.turn_conditions.append(Condition.OPTION_E) # first king selection happening on turn 0 requires some magic.
    swift.plan_learn(darklight)
    swift.set_dev_plan('Water II', 'Circuit II', 'Combat Regeneration (Geo)', 'Warp')
    swift.plan_ability_choose('King', king_choice('Train'))

    tempel.plan_learn(teyao)
    tempel.plan_attune(Element.EARTH)
    tempel.set_dev_plan('Petrification I', 'Scapegoat II', 'Augur II',  'Willpower II', 'Willpower III', 'Willpower IV', 'Soul Strike', 'Willpower V', 'Resurrection', 'Willpower Draining', 'Rapid Regen I', 'Rapid Regen II')

    teyao.plan_teach(tempel, 'Water I')
    teyao.plan_attune(Element.WATER)
    teyao.plan_trade(anemone, 1)
    teyao.plan_trade(hot, 1)
    teyao.plan_trade(darkpip, 1)
    teyao.set_dev_plan('Circuit II', 'Gold')

    wither.plan_train()
    wither.plan_attune(Element.EARTH)
    wither.set_dev_plan('Circuit II', 'Rune Crafting I', 'Rune Crafting II', 'Fire I', 'Circuit III', 'Fire II', 'Fire III', 'Cauterization', 'Hell Fire')

    Action.run_turn(GAME)


"""
Anemone:
Bunker
Attune to Warp
Warp HypoSoc

Bedna:
Teach Hotmonkey Sabotage
Fall: BlackLemonAde

BlackLemonAde:
Bunker
Body Reinforcement I: +1 surv (contingency)
Unnatural Intuition (contingency)

Coledon:
Attack Witherbrine

DarkLight:
Teach Swift-Sama Body Reinforcement I
Combat Regeneration (Hydro) (contingency)

Darkpiplumon:
Bunker
Attune to Gold

DragonLord:
Attack Witherbrine
Savior: Hotmonkey

Drasky:
Attack Bedna
Attune to Earth

Hotmonkey:
Learn from Bedna
Spy on Seventeen

HypoSoc:
Attack DarkLight
Consume Venom
Attune to Water and Fire

Lord Of Chromius:
Train
Attune to Earth

Megaolix:
Train
Attune to Earth and Water

NinetyNineLies:
Bunker
Enhanced Senses
Unnatural Intuition (contingency)

Paradosi:
Bunker
Mental Fortification I
Mental Fortification II: +1 progress
Arsonist: Coledon
Trade 3 credits to Witherbrine

PocketRikimaru:
Train
Attune to Gold
Mental Fortification I

RyoAtemi:
Bunker

Seventeen:
Train
Craft Rune: Recursion as a bonus action

Swift-Sama:
Learn from DarkLight
King: Shop

TempelJaeger:
Bunker
Attune to Earth
Mental Fortification I
Scapegoat I: Anemone

Teyao:
Heal RyoAtemi
Attune to Water

Witherbrine:
Train
Attune to Earth and Earth
"""
def turn_2():
    anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, hot, hypo, lord, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_bunker()
    anemone.plan_attune(Element.WARP)
    anemone.plan_target('Warp', hypo)

    bedna.plan_teach(hot, 'Sabotage')
    bedna.plan_target('Fall', black)

    black.plan_bunker()
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Unnatural Intuition', contingency=True)

    cole.plan_attack(wither)

    darklight.plan_teach(swift, 'Body Reinforcement I')
    darklight.plan_hydro('Combat Regeneration (Hydro)', contingency=True)

    darkpip.plan_bunker()
    darkpip.plan_attune(Element.GOLD)

    dragon.plan_attack(wither)
    dragon.plan_target('Savior', hot)

    drasky.plan_attack(bedna)
    drasky.plan_attune(Element.EARTH)

    hot.plan_learn(bedna)
    hot.plan_spy(seven)

    hypo.plan_attack(darklight)
    hypo.plan_consume_item('Venom')
    hypo.plan_attune(Element.WATER, Element.FIRE)

    lord.plan_train()
    lord.plan_attune(Element.EARTH)

    mega.plan_train()
    mega.plan_attune(Element.EARTH, Element.WATER)

    ninety.plan_bunker()
    ninety.plan_hydro('Enhanced Senses')
    ninety.plan_hydro('Unnatural Intuition', contingency=True)

    para.plan_bunker()
    para.plan_hydro('Mental Fortification I')
    para.plan_hydro('Mental Fortification II', will=[1, 0])
    para.plan_target('Arsonist', cole)
    # para.plan_trade(wither, 3) # bounced by Styx rule as they traded of their credits.

    pocket.plan_train()
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')

    ryo.plan_bunker()

    seven.plan_train()
    seven.plan_craft_rune('Recursion', bonus=True)
    seven.set_dev_plan('Willpower I', 'Body Reinforcement I', 'Body Reinforcement II')

    swift.plan_learn(darklight)
    swift.plan_ability_choose('King', king_choice('Shop'))

    tempel.plan_bunker()
    tempel.plan_attune(Element.EARTH)
    tempel.plan_hydro('Mental Fortification I')
    tempel.plan_target('Scapegoat I', anemone)

    teyao.plan_heal(ryo)
    teyao.plan_attune(Element.WATER)
    teyao.set_dev_plan('Gold', 'Water II', 'Combat Regeneration (Geo)')

    wither.plan_train()
    wither.plan_attune(Element.EARTH, Element.EARTH)

    Action.run_turn(GAME)


"""
Anemone:
Bunker
Attune to Warp
Warp DragonLord
Trade 1 credit to Drasky

Bedna:
Shop for Synthetic Weave
Fall: Paradosi

BlackLemonAde:
Shop for Lizard Tail
Body Reinforcement I: +1 surv (contingency)
Unnatural Intuition (contingency)

Coledon:

DarkLight:
Teach Swift-Sama Magical Healing (Hydro)
Combat Regeneration (Hydro) (contingency)

Darkpiplumon:
Train
Attune to Gold
Earth I

DragonLord:
Attack RyoAtemi
Savior: DragonLord

Drasky:
Shop for Synthetic Weave
Attune to Earth

Hotmonkey:
Train

HypoSoc:
Train
Attune to Water and Fire
Trade 1 Venom to NinetyNineLies
Trade 1 credit to Megaolix

Lord Of Chromius:
Shop for Synthetic Weave
Attune to Earth

Megaolix:
Attack DarkLight
Attune to Earth and Water

NinetyNineLies:
Shop for a Sword
Unnatural Intuition (contingency)

Paradosi:
Train
Mental Fortification I
Mental Fortification II: +1 progress

PocketRikimaru:
Train
Attune to Gold
Mental Fortification I

RyoAtemi:
Shop for Bunker Shields

Seventeen:
Shop for a Medkit and Shrooms
Craft Rune: Recursion as a bonus action
Trade Recursion Rune to HypoSoc
Trade Recursion Rune to Swift-Sama

Swift-Sama:
Learn from DarkLight
King: Train

TempelJaeger:
Bunker
Attune to Earth
Mental Fortification I
Scapegoat I: DragonLord

Teyao:
Heal Bedna
Attune to Water
Trade 1 credit to Bedna
Trade 1 credit to RyoAtemi
Trade 1 credit to Swift-Sama

Witherbrine:
Train
Attune to Earth and Earth
"""
def turn_3():
    anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, hot, hypo, lord, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_bunker()
    anemone.plan_attune(Element.WARP)
    anemone.plan_target('Warp', dragon)
    anemone.plan_trade(drasky, 1)

    # bounced by Styx rule as they shopped for all of their credits.
    # bedna.plan_shop('Synthetic Weave')
    # bedna.plan_target('Fall', para)

    black.plan_shop('Lizard Tail')
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Unnatural Intuition', contingency=True)

    cole

    darklight.plan_teach(swift, 'Magical Healing (Hydro)')
    darklight.plan_hydro('Combat Regeneration (Hydro)', contingency=True)
    darklight.set_dev_plan('Awareness II', 'Willpower III', 'Willpower IV', 'Soul Strike')

    darkpip.plan_train()
    darkpip.plan_attune(Element.GOLD)
    darkpip.set_dev_plan('Earth I','Awareness I')

    dragon.plan_attack(ryo)
    dragon.plan_target('Savior', dragon)
    dragon.set_dev_plan('Circuit I', 'Fire I', 'Fire II', 'Circuit II', 'Air I', 'Ash', 'Circuit III')

    drasky.plan_shop('Leather Armor', 'Bokken')
    drasky.plan_attune(Element.EARTH)

    hot.plan_train()
    hot.set_dev_plan('Attunement Detection', 'Awareness III', 'Know Thy Enemy', 'Psy Ops')

    hypo.plan_train()
    hypo.plan_attune(Element.WATER, Element.FIRE)
    hypo.plan_trade(ninety, item_names=['Venom'])
    hypo.plan_trade(mega, 1, action_condition=[mega, Attack, darklight])

    # bounced by Styx rule as they shopped for all of their credits.
    # lord.plan_shop('Synthetic Weave')
    # lord.plan_attune(Element.EARTH)

    mega.plan_attack(darklight)
    mega.plan_attune(Element.EARTH, Element.WATER)

    ninety.plan_shop('Sword')
    ninety.plan_hydro('Unnatural Intuition', contingency=True)

    para.plan_train()
    para.plan_hydro('Mental Fortification I')
    para.plan_hydro('Mental Fortification II', will=[1, 0])
    para.set_dev_plan('Willpower II', 'Body Reinforcement II', 'Body Reinforcement III')

    pocket.plan_train()
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')

    # bounced by Styx rule as they shopped for all of their credits.
    # ryo.plan_shop('Bunker Shields')

    # bounced by Styx rule as they shopped for all of their credits.
    # seven.plan_shop('Medkit', 'Shrooms')
    # seven.plan_craft_rune('Recursion', bonus=True)
    # seven.plan_trade(hypo, item_names=['Recursion Rune'])
    # seven.plan_trade(swift, item_names=['Recursion Rune'])

    swift.plan_learn(darklight)
    swift.plan_ability_choose('King', king_choice('Train'))

    tempel.plan_bunker()
    tempel.plan_attune(Element.EARTH)
    tempel.plan_hydro('Mental Fortification I')
    tempel.plan_target('Scapegoat I', dragon)

    teyao.plan_heal(bedna)
    teyao.plan_attune(Element.WATER)
    teyao.plan_trade(bedna, 1)
    teyao.plan_trade(ryo, 1)
    teyao.plan_trade(swift, 1)

    wither.plan_train()
    wither.plan_attune(Element.EARTH, Element.EARTH)

    Action.run_turn(GAME)

"""
Anemone:
Bunker

Bedna:
Teach Hotmonkey Sabotage
Spy on Witherbrine
Fall: Seventeen

BlackLemonAde:
Train
Body Reinforcement I: +1 surv (contingency)
Unnatural Intuition (contingency)

Coledon:
Train

DarkLight:
Learn from Swift-Sama
Combat Regeneration (Hydro) (contingency)

Darkpiplumon:
Train
Attune to Gold

DragonLord:
Attack Teyao

Drasky:
Attack Hotmonkey
Attune to Earth

Hotmonkey:
Learn from Bedna
Spy on Darkpiplumon

HypoSoc:
Attack Hotmonkey
Consume Venom
Attune to Water and Fire

Lord Of Chromius:
Train
Attune to Earth

Megaolix:
Attack DarkLight
Attune to Earth and Water

NinetyNineLies:
Bunker
Enhanced Senses
Unnatural Intuition (contingency)

Paradosi:
Attack Hotmonkey
Body Reinforcement I: +1 surv

PocketRikimaru:
Train
Attune to Gold
Mental Fortification I

RyoAtemi:
Bunker

Seventeen:
Attack Teyao
Craft Rune: Recursion as a bonus action
Trade Recursion Rune to HypoSoc
Trade Recursion Rune to Swift-Sama

Swift-Sama:
Teach DarkLight Circuit I
King: Shop

TempelJaeger:
Learn from Teyao
Attune to Earth
Scapegoat I: RyoAtemi

Teyao:
Teach TempelJaeger Circuit II
Attune to Water and Gold

Witherbrine:
Craft Rune: Void
Craft Rune: Void as a bonus action
"""
def turn_4():
    anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, hot, hypo, lord, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_bunker()

    bedna.plan_teach(hot, 'Sabotage')
    bedna.plan_spy(wither)
    bedna.plan_target('Fall', seven)

    black.plan_train()
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Unnatural Intuition', contingency=True)

    cole.plan_train()

    darklight.plan_learn(swift)
    darklight.plan_hydro('Combat Regeneration (Hydro)', contingency=True)

    darkpip.plan_train()
    darkpip.plan_attune(Element.GOLD)
    darkpip.set_dev_plan('Awareness I', 'Aeromancy Intuition', 'Awareness II')

    dragon.plan_attack(teyao)

    drasky.plan_attack(hot)
    drasky.plan_attune(Element.EARTH)
    drasky.set_dev_plan('Circuit II', 'Antimagic (Geo)')

    hot.plan_learn(bedna)
    hot.plan_spy(darkpip)

    hypo.plan_attack(hot)
    hypo.plan_consume_item('Venom')
    hypo.plan_attune(Element.WATER, Element.FIRE)
    hypo.set_dev_plan('Antimagic (Geo)', 'Antimagic (Aero)', 'Air I', 'Ash', 'Circuit IV', 'Mist')

    lord.plan_train()
    lord.plan_attune(Element.EARTH)

    mega.plan_attack(darklight)
    mega.plan_attune(Element.EARTH, Element.WATER)

    ninety.plan_bunker()
    ninety.plan_hydro('Unnatural Intuition', contingency=True)
    ninety.plan_hydro('Enhanced Senses')

    para.plan_attack(hot)
    para.plan_hydro('Body Reinforcement I', [0, 1])

    pocket.plan_train()
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')

    ryo.plan_bunker()

    seven.plan_attack(teyao)
    seven.plan_craft_rune('Recursion', bonus=True)
    seven.plan_trade(hypo, item_names=['Recursion Rune'])
    seven.plan_trade(swift, item_names=['Recursion Rune'])

    swift.plan_teach(darklight, 'Circuit I')
    swift.plan_ability_choose('King', king_choice('Shop'))

    tempel.plan_learn(teyao)
    tempel.plan_attune(Element.EARTH)
    tempel.plan_target('Scapegoat I', ryo)

    teyao.plan_teach(tempel, 'Circuit II')
    teyao.plan_attune(Element.WATER, Element.GOLD)

    wither.plan_craft_rune('Void')
    wither.plan_craft_rune('Void', bonus=True)
    wither.plan_attune(Element.EARTH, Element.EARTH)

    Action.run_turn(GAME)

"""
Anemone:
Bunker

Bedna:
Shop for Force Projection
Fall: Paradosi

BlackLemonAde:
Train
Body Reinforcement I: +1 surv (contingency)
Unnatural Intuition (contingency)

Coledon:
Doctor

DarkLight:
Attack Paradosi
Combat Regeneration (Hydro)

Darkpiplumon:
Shop for Synthetic Weave, Sword, and Shrooms
Attune to Gold and Earth

DragonLord:
Attack PocketRikimaru

Drasky:
Attack Lord Of Chromius
Attune to Earth

HypoSoc:
Attack Lord Of Chromius
Consume Venom
Attune to Water and Fire
Trade 1 credit to Megaolix  

Lord Of Chromius:
Shop for Synthetic Weave
Attune to Earth and Light

Megaolix:
Train
Attune to Earth and Water

NinetyNineLies:
Bunker
Unnatural Intuition (contingency)

Paradosi:
Train

PocketRikimaru:
Shop for Oblivion Ordinance, Camo Cloak, Soft, and Leather Armor
Attune to Gold
Mental Fortification I

RyoAtemi:
Bunker

Seventeen:
Attack TempelJaeger
Craft Rune: Recursion as a bonus action
Trade Recursion Rune to DarkLight

Swift-Sama:
Shop for Soft, Soft, Soft
King: Train

TempelJaeger:
Shop for Automata (Do you have a source on that? Source? A source. I need a source. Sorry, I mean I need a source that explicitly states your argument. This is just tangential to the discussion. No, you can't make inferences and observations from the sources you've gathered. Any additional comments from you MUST be a subset of the information from the sources you've gathered. You can't make normative statements from empirical evidence. Do you have a degree in that field? A Polyhistor degree? In that field? Then your arguments are invalid. No, it doesn't matter how close those data points are correlated. Correlation does not equal causation. Correlation does not equal causation. CORRELATION. DOES. NOT. EQUAL. CAUSATION. You still haven't provided me a valid source yet. Nope, still haven't.)
Attune to Earth
Scapegoat I: BlackLemonAde

Teyao:
Shop for Gas Mask, Poison Gas, and Poison Gas

Witherbrine:
Attack DarkLight
Craft Rune: Void as a bonus action
Attune to Earth and Fire
Consume Void Rune
"""
def turn_5():
    anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, _ , hypo, lord, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_bunker()

    # bounced by Styx rule as they shopped for all of their credits.
    # bedna.plan_shop('Force Projection')
    # bedna.plan_target('Fall', para)

    black.plan_train()
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Unnatural Intuition', contingency=True)

    cole.plan_doctor()

    darklight.plan_attack(para)
    darklight.plan_hydro('Combat Regeneration (Hydro)')

    darkpip.plan_shop('Synthetic Weave', 'Sword', 'Shrooms')
    darkpip.plan_attune(Element.GOLD, Element.EARTH)

    dragon.plan_attack(pocket)

    drasky.plan_attack(lord)
    drasky.plan_attune(Element.EARTH)
    drasky.set_dev_plan('Antimagic (Geo)', 'Martial Arts III', 'Armor Break')

    hypo.plan_attack(lord)
    hypo.plan_consume_item('Venom')
    hypo.plan_attune(Element.WATER, Element.FIRE)
    hypo.plan_trade(mega, 1)

    lord.plan_shop('Synthetic Weave')
    lord.plan_attune(Element.EARTH, Element.LIGHT)

    mega.plan_train()
    mega.plan_attune(Element.EARTH, Element.WATER)

    ninety.plan_bunker()
    ninety.plan_hydro('Unnatural Intuition', contingency=True)
    ninety.set_dev_plan('Body Reinforcement I', 'Body Reinforcement II', 'Body Reinforcement III', 'Willpower II', 'Will Armor I')

    para.plan_train()
    para.plan_hydro('Mental Fortification I')

    pocket.plan_shop('Oblivion Ordinance', 'Camo Cloak', 'Soft', 'Leather Armor')
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')

    ryo.plan_bunker()

    seven.plan_attack(tempel)
    seven.plan_craft_rune('Recursion', bonus=True)
    seven.plan_trade(darklight, item_names=['Recursion Rune'])

    # bounced by Styx rule as they shopped for all of their credits.
    # swift.plan_shop('Soft', 'Soft', 'Soft')
    # swift.plan_ability_choose('King', king_choice('Train'))
    swift.plan_ability_choose('King', king_choice('none'))

    # bounced by Styx rule as they shopped for all of their credits.
    tempel.plan_shop('Automata', automata_name=["Do you have a source on that? Source? A source. I need a source. Sorry, I mean I need a source that explicitly states your argument. This is just tangential to the discussion. No, you can't make inferences and observations from the sources you've gathered. Any additional comments from you MUST be a subset of the information from the sources you've gathered. You can't make normative statements from empirical evidence. Do you have a degree in that field? A Polyhistor degree? In that field? Then your arguments are invalid. No, it doesn't matter how close those data points are correlated. Correlation does not equal causation. Correlation does not equal causation. CORRELATION. DOES. NOT. EQUAL. CAUSATION. You still haven't provided me a valid source yet. Nope, still haven't."])
    tempel.plan_attune(Element.EARTH)
    tempel.plan_target('Scapegoat I', black)
    tempel.set_dev_plan('Willpower II', 'Willpower III', 'Willpower IV', 'Resurrection', 'Willpower V', 'Willpower Draining', 'Scapegoat II', 'Rapid Regen I', 'Rapid Regen II', 'Augur II', 'Soul Strike')

    teyao.plan_shop('Gas Mask', 'Poison Gas', 'Poison Gas')

    wither.plan_attack(darklight)
    wither.plan_craft_rune('Void', bonus=True)
    wither.plan_attune(Element.EARTH, Element.FIRE)
    wither.plan_consume_item('Void Rune')
    wither.set_dev_plan('Circuit III', 'Fire II', 'Fire III', 'Earth III', 'Circuit IV', 'Circuit V', 'Circuit VI')

    Action.run_turn(GAME)

"""
Anemone:
Bunker

Bedna:
Train
Spy on NinetyNineLies
Fall: PocketRikimaru

BlackLemonAde:
Train
Body Reinforcement I: +1 surv (contingency)
Unnatural Intuition (contingency)

Coledon:

DarkLight:
Bunker

Darkpiplumon:
Attack NinetyNineLies
Attune to Gold, Earth
Consume Shrooms

DragonLord:
Train

Drasky:
Attack NinetyNineLies
Attune to Earth

HypoSoc:
Tattoo Rune Crafting II on self
Consume Recursion Rune
Attune to Fire, Water
Trade 1 Venom to Drasky

Megaolix:
Train
Attune to Earth, Water

NinetyNineLies:
Bunker
Enhanced Senses
Unnatural Intuition (contingency)

Paradosi:
Train
Mental Fortification I
Body Reinforcement I: +1 surv (contingency)
Arsonist: Teyao

PocketRikimaru:
Train
Attune to Gold
Mental Fortification I

RyoAtemi:
Bunker

Seventeen:
Attack Paradosi
Craft Rune: Martial Arts III as a bonus action

Swift-Sama:
Train
King: Shop

TempelJaeger:
Bunker
Attune to Earth
Mental Fortification I
Scapegoat I: Paradosi

Teyao:
Attack Seventeen
Attune to Water, Gold
Trade 1 credit to Anemone

Witherbrine:
Craft Rune: Void
Craft Rune: Void as a bonus action
Attune to Earth, Earth, Fire
Consume Void Rune
"""
def turn_6():
    anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, _, hypo, _, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_bunker()

    bedna.plan_train()
    bedna.plan_spy(ninety)
    bedna.plan_target('Fall', pocket)
    bedna.set_dev_plan('Bolthole', 'Aeromancy Intuition')

    black.plan_train()
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Unnatural Intuition', contingency=True)
    black.set_dev_plan('Body Reinforcement II', 'Body Reinforcement III', 'Willpower II')

    cole

    darklight.plan_bunker()

    darkpip.plan_attack(ninety)
    darkpip.plan_attune(Element.GOLD, Element.EARTH)
    darkpip.plan_consume_item('Shrooms')
    darkpip.set_dev_plan('Awareness I', 'Aeromancy Intuition')

    dragon.plan_train()

    drasky.plan_attack(ninety)
    drasky.plan_attune(Element.EARTH)
    drasky.set_dev_plan('Antimagic (Geo)', 'Martial Arts III', 'Armor Break', 'Circuit III')

    hypo.plan_tattoo(hypo, 'Rune Crafting II')
    hypo.plan_consume_item('Recursion Rune')
    hypo.plan_attune(Element.FIRE, Element.WATER)
    hypo.plan_trade(drasky, item_names=['Venom'])

    mega.plan_train()
    mega.plan_attune(Element.EARTH, Element.WATER)

    ninety.plan_bunker()
    ninety.plan_hydro('Unnatural Intuition', contingency=True)
    ninety.plan_hydro('Enhanced Senses')

    para.plan_train()
    para.plan_hydro('Mental Fortification I')
    para.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    para.plan_target('Arsonist', teyao)

    pocket.plan_train()
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')

    ryo.plan_bunker()

    seven.plan_attack(para)
    seven.plan_craft_rune('Martial Arts III', bonus=True)

    swift.plan_train()
    swift.plan_ability_choose('King', king_choice('Shop'))

    tempel.plan_bunker()
    tempel.plan_attune(Element.EARTH)
    tempel.plan_hydro('Mental Fortification I')
    tempel.plan_target('Scapegoat I', para)
    tempel.set_dev_plan('Willpower II', 'Willpower III', 'Willpower IV', 'Resurrection', 'Willpower V', 'Willpower Draining', 'Scapegoat II', 'Rapid Regen I', 'Rapid Regen II', 'Augur II', 'Soul Strike')

    teyao.plan_attack(seven)
    teyao.plan_attune(Element.WATER, Element.GOLD)
    teyao.plan_trade(anemone, 1)

    wither.plan_craft_rune('Void')
    wither.plan_craft_rune('Void', bonus=True)
    wither.plan_attune(Element.EARTH, Element.EARTH, Element.FIRE)
    wither.plan_consume_item('Void Rune')
    wither.set_dev_plan('Antimagic (Hydro)', 'Fire II', 'Fire III', 'Earth III', 'Circuit IV', 'Circuit V', 'Circuit VI')

    Action.run_turn(GAME)

"""
Anemone:
Bunker

Bedna:
Train
Disable Sabotage
Fall: TempelJaeger

BlackLemonAde:
Train
Body Reinforcement I: +1 surv (contingency)
Body Reinforcement II: +3 surv (contingency)
Unnatural Intuition (contingency)

Coledon:

DarkLight:
Bunker
Combat Regeneration (Hydro) (contingency)

Darkpiplumon:
Train
Attune to Gold and Earth

DragonLord:
Attack Bedna

Drasky:
Go to class

HypoSoc:
Go to class
Craft Toxin Rune as a bonus action
Trade Toxin Rune to Seventeen
Trade 1 credit to Megaolix if Megaolix attacks DarkLight

Megaolix:
Attack DarkLight
Attune to Earth and Water

NinetyNineLies:
Bunker
Unnatural Intuition (contingency)

Paradosi:
Doctor
Mental Fortification I
Body Reinforcement I: +1 surv (contingency)

PocketRikimaru:
Shop for Liquid Memories, Liquid Memories, Liquid Memories, Bokken
Attune to Gold
Mental Fortification I

RyoAtemi:
Learn from Teyao

Seventeen:
Shop for Sword, Medkit
Craft Martial Arts III Rune as a bonus action

Swift-Sama:
Tattoo Rune Crafting II on self
Consume Recursion Rune
Attune to Water and Water
King: Train

TempelJaeger:
Bunker
Attune to Earth
Mental Fortification I
Scapegoat I: Bedna

Teyao:
Teach RyoAtemi Circuit I
Attune to Water and Gold

Witherbrine:
Shop for Healing Tank
Craft Fire I Rune as a bonus action
Attune to Earth, Earth, Fire
Consume Void Rune
"""
def turn_7():
    anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, _, hypo, _, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_bunker()

    bedna.plan_train()
    bedna.disable_ability('Sabotage')
    bedna.plan_target('Fall', tempel)

    black.plan_train()
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Body Reinforcement II', [0, 3], contingency=True)
    black.plan_hydro('Unnatural Intuition', contingency=True)

    cole

    darklight.plan_bunker()
    darklight.plan_hydro('Combat Regeneration (Hydro)', contingency=True)

    darkpip.plan_train()
    darkpip.plan_attune(Element.GOLD, Element.EARTH)
    darkpip.set_dev_plan('Aeromancy Intuition', 'Awareness II', 'Know Thy Enemy')

    dragon.plan_attack(bedna)

    drasky.plan_class()
    drasky.set_dev_plan('Antimagic (Geo)', 'Fast Attune I', 'Martial Arts III', 'Armor Break', 'Circuit III')

    hypo.plan_class()
    hypo.plan_craft_rune('Toxin', bonus=True)
    hypo.plan_trade(seven, item_names=['Toxin Rune'])
    hypo.plan_trade(mega, 1, action_condition=[mega, Attack, darklight])

    mega.plan_attack(darklight)
    mega.plan_attune(Element.EARTH, Element.WATER)

    ninety.plan_bunker()
    ninety.plan_hydro('Unnatural Intuition', contingency=True)

    para.plan_doctor()
    para.plan_hydro('Mental Fortification I')
    para.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)

    pocket.plan_shop('Liquid Memories', 'Liquid Memories', 'Liquid Memories', 'Bokken')
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')

    ryo.plan_learn(teyao)

    seven.plan_shop('Sword', 'Medkit')
    seven.plan_craft_rune('Martial Arts III', bonus=True)

    swift.plan_tattoo(swift, 'Rune Crafting II')
    swift.plan_consume_item('Recursion Rune')
    swift.plan_attune(Element.WATER, Element.WATER)
    swift.plan_ability_choose('King', king_choice('Train'))

    tempel.plan_bunker()
    tempel.plan_attune(Element.EARTH)
    tempel.plan_hydro('Mental Fortification I')
    tempel.plan_target('Scapegoat I', bedna)
    tempel.set_dev_plan('Willpower II', 'Willpower III', 'Willpower IV', 'Resurrection', 'Willpower V', 'Willpower Draining', 'Scapegoat II', 'Rapid Regen I', 'Rapid Regen II', 'Augur II', 'Soul Strike')

    teyao.plan_teach(ryo, 'Circuit I')
    teyao.plan_attune(Element.WATER, Element.GOLD)

    # bounced by Styx rule as they shopped for all of their credits.
    # wither.plan_shop('Healing Tank')
    # wither.plan_craft_rune('Fire I', bonus=True)
    # wither.plan_attune(Element.EARTH, Element.EARTH, Element.FIRE)
    # wither.plan_consume_item('Void Rune')
    wither.set_dev_plan('Runic Tattoos', 'Circuit IV', 'Earth III', 'Fire II', 'Circuit V', 'Circuit VI')

    Action.run_turn(GAME)

"""
Anemone:
Bunker
Trade 1 credit to Drasky

Bedna:
Bunker
Spy on Seventeen
Fall: PocketRikimaru

BlackLemonAde:
Train
Body Reinforcement I: +1 surv (contingency)
Body Reinforcement II: +3 surv (contingency)

Coledon:
Train

DarkLight:
Learn from Seventeen

Darkpiplumon:
Attack RyoAtemi
Attune to Gold, Earth

DragonLord:
Attack Bedna

Drasky:
Attack Swift-Sama

HypoSoc:
Attack Swift-Sama
Attune to Fire, Water
Craft Toxin Rune as a bonus action
Trade 1 Venom to Teyao if Teyao attacks trades 1 credit to HypoSoc

Megaolix:
Attack NinetyNineLies
Attune to Earth, Water

NinetyNineLies:
Bunker
Unnatural Intuition
Enhanced Senses

Paradosi:
Bunker
Mental Fortification I
Body Reinforcement I: +1 surv (contingency)
Arsonist: Megaolix

PocketRikimaru:
Attack HypoSoc
Attune to Gold
Mental Fortification I
Consume Liquid Memories

RyoAtemi:
Bunker

Seventeen:
Teach DarkLight Martial Arts I
Craft Martial Arts III Rune as a bonus action
Trade Martial Arts III Rune to DarkLight

Swift-Sama:
Train
Craft King Rune as a bonus action
Attune to Water, Water
King: Shop

TempelJaeger:
Bunker
Attune to Earth
Mental Fortification I
Scapegoat I: Bedna

Teyao:
Heal Bedna
Attune to Water, Gold

Witherbrine:
Train
Craft Fire I Rune as a bonus action
Attune to Earth, Earth, Fire
Consume Void Rune
"""
def turn_8():
    anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, _, hypo, _, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_bunker()
    anemone.plan_trade(drasky, 1)

    bedna.plan_bunker()
    bedna.plan_spy(seven)
    bedna.plan_target('Fall', pocket)

    black.plan_train()
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Body Reinforcement II', [0, 3], contingency=True)

    cole.plan_train()

    darklight.plan_learn(seven)

    darkpip.plan_attack(ryo)
    darkpip.plan_attune(Element.GOLD, Element.EARTH)

    dragon.plan_attack(bedna)

    drasky.plan_attack(swift)
    drasky.set_dev_plan('Antimagic (Geo)', 'Martial Arts III', 'Armor Break', 'Forged in Fire')

    hypo.plan_attack(swift)
    hypo.plan_attune(Element.WATER, Element.FIRE)
    hypo.plan_craft_rune('Toxin', bonus=True)
    hypo.plan_trade(teyao, item_names=['Venom'], action_condition=[teyao, Trade, hypo, 1])
    # hypo.plan_trade(para, 4) # bounced by Styx rule as they traded all of their credits.

    mega.plan_attack(ninety)
    mega.plan_attune(Element.EARTH, Element.WATER)

    ninety.plan_bunker()
    ninety.plan_hydro('Unnatural Intuition')
    ninety.plan_hydro('Enhanced Senses')

    para.plan_bunker()
    para.plan_hydro('Mental Fortification I')
    para.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    para.plan_target('Arsonist', mega)

    pocket.plan_attack(hypo)
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')
    pocket.plan_consume_item('Liquid Memories')

    ryo.plan_bunker()

    seven.plan_teach(darklight, 'Martial Arts I')
    seven.plan_craft_rune('Martial Arts III', bonus=True)
    seven.plan_trade(darklight, item_names=['Martial Arts III Rune'])
    seven.set_dev_plan('Willpower I', 'Body Reinforcement I', 'Body Reinforcement II', 'Body Reinforcement III', 'Willpower II')

    swift.plan_train()
    swift.plan_craft_rune('King', bonus=True)
    swift.plan_attune(Element.WATER, Element.WATER)
    swift.plan_ability_choose('King', king_choice('Shop'))

    tempel.plan_bunker()
    tempel.plan_attune(Element.EARTH)
    tempel.plan_hydro('Mental Fortification I')
    tempel.plan_target('Scapegoat I', bedna)

    teyao.plan_heal(bedna)
    teyao.plan_attune(Element.WATER, Element.GOLD)
    teyao.set_dev_plan('Combat Regeneration (Geo)', 'Circuit III', 'Quiet Attune') 

    wither.plan_train()
    wither.plan_craft_rune('Fire I', bonus=True)
    wither.plan_attune(Element.EARTH, Element.EARTH, Element.FIRE)
    wither.plan_consume_item('Void Rune')
    wither.set_dev_plan('Runic Tattoos', 'Circuit IV', 'Earth III', 'Fire II', 'Circuit V', 'Cauterization', 'Hell fire', 'Awareness I', 'Aeromancy Intuition')

    Action.run_turn(GAME)

    return [(player.name, player.conditions, player.progress_dict) for player in [anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, hypo, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither]]


"""
"""
def turn_9(statuses):
    anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, _, hypo, _, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    cole.plan_nothing()

    ninety.plan_class()

    swift.plan_ability_choose('King', king_choice('none'))

    Action.run_turn(GAME)

    for name, conditions, progress_dict in statuses:
        player = GAME.get_player(name)
        player.conditions = conditions
        player.progress_dict = progress_dict

"""
Anemone:
Bunker

Bedna:
Train
Spy on HypoSoc
Fall: Anemone

BlackLemonAde:
Train
Body Reinforcement I: +1 surv (contingency)
Body Reinforcement II: +3 surv (contingency)
Unnatural Intuition (contingency)

Coledon:
Train

DarkLight:
Bunker
Combat Regeneration (Hydro)
Consume Martial Arts III Rune
Trade 7 credits to DragonLord

Darkpiplumon:
Attack DarkLight
Attune to Gold, Earth

DragonLord:
Attack NinetyNineLies

Drasky:
Attack PocketRikimaru
Attune to Earth

HypoSoc:
Attack Swift-Sama
Attune to Fire, Water
Craft Fire I Rune as a bonus action
Consume Venom
Trade 1 Venom to Teyao if Teyao attacks trades 1 credit to HypoSoc
Trade a Fire I Rune to Drasky

Megaolix:
Train
Attune to Earth, Water

NinetyNineLies:
Bunker
Unnatural Intuition
Enhanced Senses

Paradosi:
Train
Mental Fortification I
Mental Fortification II: +1 progress
Body Reinforcement I: +1 surv (contingency)

PocketRikimaru:
Bunker
Attune to Gold
Mental Fortification I

RyoAtemi:
Bunker

Seventeen:
Attack Bedna
Craft Body Reinforcement I Rune as a bonus action
Body Reinforcement I: +1/+1 
Consume Toxin Rune

Swift-Sama:
Train
Craft King Rune as a bonus action
Attune to Water, Water
King: Shop

TempelJaeger:
Attack Bedna
Attune to Earth
Mental Fortification I
Scapegoat I: Bedna

Teyao:
Attack NinetyNineLies
Attune to Water, Water
Trade 1 credit to HypoSoc if HypoSoc trades 1 Venom to Teyao

Witherbrine:
Tattoo Void Rune on self
Craft Fire I Rune as a bonus action
Attune to Earth, Earth, Fire
Consume Void Rune
"""
def turn_10():
    anemone, bedna, black, cole, darklight, darkpip, dragon, drasky, _, hypo, _, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_bunker()

    bedna.plan_train()
    bedna.plan_spy(hypo)
    bedna.plan_target('Fall', anemone)
    bedna.set_dev_plan('Bolthole', 'Aeromancy Intuition', 'Know Thy Enemy', 'Psy Ops', 'Awareness III')

    black.plan_train()
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Body Reinforcement II', [0, 3], contingency=True)
    black.plan_hydro('Unnatural Intuition', contingency=True)
    black.set_dev_plan('Body Reinforcement III', 'Willpower II', 'Awareness I')

    cole.plan_train()

    darklight.plan_bunker()
    darklight.plan_hydro('Combat Regeneration (Hydro)')
    darklight.plan_consume_item('Martial Arts III Rune')
    # darklight.plan_trade(dragon, 7) # bounced by Styx rule as they traded all of their credits.

    darkpip.plan_attack(darklight)
    darkpip.plan_attune(Element.GOLD, Element.EARTH)

    dragon.plan_attack(ninety)

    drasky.plan_attack(pocket)
    drasky.plan_attune(Element.EARTH)
    drasky.set_dev_plan('Antimagic (Geo)', 'Martial Arts III', 'Circuit III')

    hypo.plan_attack(swift)
    hypo.plan_attune(Element.WATER, Element.FIRE)
    hypo.plan_craft_rune('Fire I', bonus=True)
    hypo.plan_consume_item('Venom')
    hypo.plan_trade(teyao, item_names=['Venom'])
    hypo.plan_trade(drasky, item_names=['Fire I Rune'])

    mega.plan_train()
    mega.plan_attune(Element.EARTH, Element.WATER)
    mega.set_dev_plan('Air I', 'Quiet Attune', 'Speed (Geo) I', 'Awareness I')

    ninety.plan_bunker()
    ninety.plan_hydro('Unnatural Intuition')
    ninety.plan_hydro('Enhanced Senses')

    para.plan_train()
    para.plan_hydro('Mental Fortification I')
    para.plan_hydro('Mental Fortification II', will=[1, 0])
    para.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    para.set_dev_plan('Body Reinforcement II', 'Mental Fortification III', 'Rapid Regen I', 'Rapid Regen II')

    pocket.plan_bunker()
    pocket.plan_hydro('Mental Fortification I')
    pocket.plan_attune(Element.GOLD)
    pocket.plan_consume_item('Liquid Memories')

    ryo.plan_bunker()

    seven.plan_attack(bedna)
    seven.plan_craft_rune('Body Reinforcement I', bonus=True)
    seven.plan_hydro('Body Reinforcement I', will=[1, 1])
    seven.plan_consume_item('Toxin Rune')

    swift.plan_train()
    swift.plan_craft_rune('King', bonus=True)
    swift.plan_attune(Element.WATER, Element.WATER)
    swift.plan_ability_choose('King', king_choice('Shop'))

    tempel.plan_attack(bedna)
    tempel.plan_attune(Element.EARTH)
    tempel.plan_hydro('Mental Fortification I')
    tempel.plan_target('Scapegoat I', bedna)
    tempel.set_dev_plan('Willpower III', 'Willpower IV', 'Resurrection', 'Rapid Regen I', 'Rapid Regen II', 'Mental Fortification II', 'Scapegoat II', 'Mental Fortification III', 'Body Reinforcement I', 'Speed (Hydro) I', 'Speed (Hydro) II', 'Willpower V', 'Willpower Draining', 'Scapegoat III', 'Scapegoat IV', 'Augur II', 'Augur III', 'Augur IV')

    teyao.plan_attack(ninety)
    teyao.plan_attune(Element.WATER, Element.WATER)
    teyao.plan_trade(hypo, 1)

    wither.plan_tattoo(wither, 'Void')
    wither.plan_craft_rune('Fire I', bonus=True)
    wither.plan_attune(Element.EARTH, Element.EARTH, Element.FIRE)
    wither.plan_consume_item('Void Rune')
    wither.set_dev_plan('Earth III', 'Fire II', 'Circuit V', 'Petrification I', 'Cauterization', 'Hell Fire', 'Awareness I', 'Aeromancy Intuition')

    Action.run_turn(GAME)

"""
Anemone:
Bunker

BlackLemonAde:
Train
Body Reinforcement I: +1 surv (contingency)
Body Reinforcement II: +3 surv (contingency)
Body Reinforcement III: +5 surv (contingency)
Unnatural Intuition (contingency)

Cole:

DarkLight:
Attack Darkpiplumon
Combat Regeneration (Hydro)
Trade 8 credits to DragonLord

Darkpiplumon:
Attack DarkLight
Attune to Gold, Earth

DragonLord:

Drasky:
Class

HypoSoc:
Attack Swift-Sama
Craft Toxin Rune as a bonus action
Attune to Water, Fire
Consume Venom
Trade 1 Toxin Rune to Seventeen
Trade 1 credit to NinetyNineLies

Megaolix:
Class

NinetyNineLies:
Bunker
Unnatural Intuition (contingency)

Paradosi:
Shop for Sword, Synthetic Weave, Booby Trap
Mental Fortification I
Mental Fortification II: +1 progress
Body Reinforcement I: +1 surv (contingency)

PocketRikimaru:
Bunker
Attune to Gold
Mental Fortification I
Consume Liquid Memories

RyoAtemi:
Class

Seventeen:
Attack NinetyNineLies
Consume Medkit, Body Reinforcement I Rune
Heal self
body Reinforcement I: +1/+1

Swift-Sama:
Attack Witherbrine
Craft King Rune as a bonus action
Attune to Water, Water
King: Train

TempelJaeger:
Attack PocketRikimaru
Mental Fortification I
Resurrection
Scapegoat I: self
Bounty: RyoAtemi (2)

Teyao:
Shop for Chronoshift Bomb, Shrooms, Shrooms

Witherbrine:
Train
Craft Fire I Rune as a bonus action
Attune to Earth, Earth, Fire
"""
def turn_11():
    anemone, _ , black, cole, darklight, darkpip, dragon, drasky, _, hypo, _, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_bunker()

    black.plan_train()
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Body Reinforcement II', [0, 3], contingency=True)
    black.plan_hydro('Body Reinforcement III', [0, 5], contingency=True)
    black.plan_hydro('Unnatural Intuition', contingency=True)

    cole.plan_nothing()

    darklight.plan_attack(darkpip)
    darklight.plan_hydro('Combat Regeneration (Hydro)')
    # darklight.plan_trade(dragon, 8) # bounced by Styx rule as they traded all of their credits.

    darkpip.plan_attack(darklight)
    darkpip.plan_attune(Element.GOLD, Element.EARTH)

    dragon

    drasky.plan_class()

    hypo.plan_attack(swift)
    hypo.plan_craft_rune('Toxin', bonus=True)
    hypo.plan_attune(Element.WATER, Element.FIRE)
    hypo.plan_consume_item('Venom')
    hypo.plan_trade(seven, item_names=['Toxin Rune'])
    hypo.plan_trade(ninety, 1)

    mega.plan_class()

    ninety.plan_bunker()
    ninety.plan_hydro('Unnatural Intuition', contingency=True)

    # bounced by Styx rule as they shopped for all of their credits.
    # para.plan_shop('Sword', 'Synthetic Weave', 'Booby Trap')
    # para.plan_hydro('Mental Fortification I')
    # para.plan_hydro('Mental Fortification II', will=[1, 0])
    # para.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    para.set_dev_plan('Body Reinforcement II', 'Rapid Regen I', 'Rapid Regen II')

    pocket.plan_bunker()
    pocket.plan_hydro('Mental Fortification I')
    pocket.plan_attune(Element.GOLD)
    pocket.plan_consume_item('Liquid Memories')

    ryo.plan_class()

    seven.plan_attack(ninety)
    seven.plan_consume_item('Medkit', 'Body Reinforcement I Rune')
    seven.plan_heal(seven, bonus=True)
    seven.plan_hydro('Body Reinforcement I', will=[1, 1])

    swift.plan_attack(wither)
    swift.plan_craft_rune('King', bonus=True)
    swift.plan_attune(Element.WATER, Element.WATER)
    swift.plan_ability_choose('King', king_choice('Train'))

    tempel.plan_attack(pocket)
    tempel.plan_hydro('Mental Fortification I')
    tempel.plan_hydro('Resurrection')
    tempel.plan_target('Scapegoat I', tempel)
    tempel.plan_bounty(ryo, 2)
    tempel.set_dev_plan('Rapid Regen I', 'Rapid Regen II', 'Mental Fortification II', 'Scapegoat II', 'Mental Fortification III', 'Body Reinforcement I', 'Speed (Hydro) I', 'Speed (Hydro) II', 'Willpower V', 'Willpower Draining', 'Scapegoat III', 'Scapegoat IV', 'Augur II', 'Augur III', 'Augur IV')

    teyao.plan_shop('Chronoshift Bomb', 'Shrooms', 'Shrooms')

    wither.plan_train()
    wither.plan_craft_rune('Fire I', bonus=True)
    wither.plan_attune(Element.EARTH, Element.EARTH, Element.FIRE)
    wither.set_dev_plan('Earth III', 'Fire II', 'Circuit V', 'Cauterization', 'Hell Fire', 'Awareness I', 'Aeromancy Intuition')

    Action.run_turn(GAME)

"""
Anemone:
Craft Shrooms
Bunker as a bonus action
Hydro: Crafting I
Attune to Warp
Warps TempelJaeger

BlackLemonAde:
Train
Body Reinforcement I: +1 surv (contingency)
Body Reinforcement II: +3 surv (contingency)
Body Reinforcement III: +5 surv (contingency)
Unnatural Intuition (contingency)

Coledon:

DarkLight:
Tattoo Rune Crafting II on self
Hydro: Combat Regeneration (Hydro) (contingency)
Consume Recursion Rune
Trade 8 credits to DragonLord

Darkpiplumon:
Attack DarkLight
Attune to Gold, Earth

DragonLord:
Attack TempelJaeger
Savior: self

Drasky:
Attack Megaolix
Attune to Earth
Consume Venom

HypoSoc:
Attack Megaolix
Craft Fire I Rune as a bonus action
Attune to Water, Fire, Anti
Consume Venom

Megaolix:
Bunker
Attune to Earth, Water, Air

NinetyNineLies:
Bunker
Unnatural Intuition
Enhanced Senses
Trade 2 credits to Seventeen if Seventeen attacks HypoSoc or Drasky

Paradosi:
Train
Mental Fortification I
Mental Fortification II: +1 progress
Body Reinforcement I: +1 surv
Arsonist: Witherbrine

PocketRikimaru:
Bunker
Attune to Gold
Mental Fortification I

RyoAtemi:
Learn from Teyao

Seventeen:
Heal self
Craft Body Reinforcement I Rune as a bonus action
Consume Medkit
Trade Sword to HypoSoc

Swift-Sama:
Attack Witherbrine
Craft King Rune as a bonus action
Attune to Water, Water
King: Class

TempelJaeger:
Bunker
Attune to Earth
Mental Fortification I
Resurrection
Scapegoat I: Seventeen

Teyao:
Teach RyoAtemi Water I
Attune to Water, Water
Consume Shrooms, Chronoshift Bomb

Witherbrine:
Attack NinetyNineLies, DarkLight, Coledon
Craft Fire II Rune as a bonus action
Attune to Earth, Earth, Earth, Fire
Consume Fire I Rune
"""
def turn_12():
    anemone, _ , black, cole, darklight, darkpip, dragon, drasky, _, hypo, _, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_craft('Shrooms')
    anemone.plan_bunker(bonus=True)
    anemone.plan_hydro('Crafting I')
    anemone.plan_attune(Element.WARP)
    anemone.plan_target('Warp', tempel)

    black.plan_train()
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Body Reinforcement II', [0, 3], contingency=True)
    black.plan_hydro('Body Reinforcement III', [0, 5], contingency=True)
    black.plan_hydro('Unnatural Intuition', contingency=True)

    cole.plan_nothing()

    darklight.plan_tattoo(darklight, 'Rune Crafting II')
    darklight.plan_hydro('Combat Regeneration (Hydro)', contingency=True)
    darklight.plan_consume_item('Recursion Rune')
    # darklight.plan_trade(dragon, 8) # bounced by Styx rule as they traded all of their credits.

    darkpip.plan_attack(darklight)
    darkpip.plan_attune(Element.GOLD, Element.EARTH)

    dragon.plan_attack(tempel)
    dragon.plan_target('Savior', dragon)
    dragon.set_dev_plan('Willpower I', 'Mental Fortification I', 'Mental Fortification II')

    drasky.plan_attack(mega)
    drasky.plan_attune(Element.EARTH)
    drasky.plan_consume_item('Venom')

    hypo.plan_attack(mega)
    hypo.plan_craft_rune('Fire I', bonus=True)
    hypo.plan_attune(Element.WATER, Element.FIRE, Element.ANTI)
    hypo.plan_consume_item('Venom')

    mega.plan_bunker()
    mega.plan_attune(Element.EARTH, Element.WATER, Element.AIR)

    ninety.plan_bunker()
    ninety.plan_hydro('Unnatural Intuition')
    ninety.plan_hydro('Enhanced Senses')
    ninety.plan_trade(seven, 2, action_condition=[seven, Attack, hypo]) # also checking if they attack Drasky. 

    para.plan_train()
    para.plan_hydro('Mental Fortification I')
    para.plan_hydro('Mental Fortification II', will=[1, 0])
    para.plan_hydro('Body Reinforcement I', [0, 1])
    para.plan_target('Arsonist', wither)

    pocket.plan_bunker()
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')

    ryo.plan_learn(teyao)

    seven.plan_heal(seven)
    seven.plan_craft_rune('Body Reinforcement I', bonus=True)
    seven.plan_consume_item('Medkit')
    seven.plan_trade(hypo, item_names=['Sword'])

    swift.plan_attack(wither)
    swift.plan_craft_rune('King', bonus=True)
    swift.plan_attune(Element.WATER, Element.WATER)
    swift.plan_ability_choose('King', king_choice('class'))
    swift.plan_ability_choose('King', king_choice('None'), for_rune=True)

    tempel.plan_bunker()
    tempel.plan_attune(Element.EARTH)
    tempel.plan_hydro('Mental Fortification I')
    tempel.plan_hydro('Resurrection')
    tempel.plan_target('Scapegoat I', seven)
    tempel.set_dev_plan('Mental Fortification II', 'Soul Strike', 'Willpower V', 'Scapegoat II', 'Mental Fortification III', 'Body Reinforcement I', 'Speed (Hydro) I', 'Speed (Hydro) II', 'Willpower Draining', 'Scapegoat III', 'Scapegoat IV', 'Augur II', 'Augur III', 'Augur IV')

    teyao.plan_teach(ryo, 'Water I')
    teyao.plan_attune(Element.WATER, Element.WATER)
    teyao.plan_consume_item('Shrooms', 'Chronoshift Bomb')
    teyao.set_dev_plan('Circuit III', 'Antimagic (Hydro)', 'Circuit IV', 'Antimagic (Geo)')

    wither.plan_attack(ninety, darklight, cole)
    wither.plan_craft_rune('Fire II', bonus=True)
    wither.plan_attune(Element.EARTH, Element.EARTH, Element.EARTH, Element.FIRE)
    wither.plan_consume_item('Fire I Rune')

    Action.run_turn(GAME)

"""
Anemone:
Class
Trade Shrooms to Drasky

BlackLemonAde:
Train
Body Reinforcement I: +1 surv (contingency)
Body Reinforcement II: +3 surv (contingency)
Body Reinforcement III: +5 surv (contingency)
Unnatural Intuition (contingency)

Coledon:

DarkLight:
Class
Combat Regeneration (Hydro) (contingency)
Trade 9 credits to DragonLord

Darkpiplumon:
Shop for Liquid Memories, Liquid Memories, Cheat Sheet, Paperwork
Attune to Gold, Earth

DragonLord:
Class

Drasky:
Shop for Chronoshift Bomb, Shrooms

HypoSoc:
Shop for Chronoshift Bomb
Craft Toxin Rune as a bonus action
Attune to Water, Fire
Trade 1 Venom to Drasky

Megaolix:
Shop for Liquid Memories, Medkit, Caltrops, Venom
Attune to Earth, Water, Air

NinetyNineLies:
Shop for Liquid Memories, Cheat Sheet
Unnatural Intuition (contingency)

Paradosi:
Class
Mental Fortification II: +1 Academics
Body Reinforcement I: +1 surv (contingency)
Body Reinforcement II: +3 surv (contingency)

PocketRikimaru:
Shop for Lizard Tail, Lizard Tail, Lizard Tail, Ablative Ossification
Attune to Gold
Mental Fortification I

RyoAtemi:
Shop for Chronoshift Bomb, Ablative Ossification
Attune to Water

Seventeen:
Attack RyoAtemi
Craft Body Reinforcement I Rune as a bonus action
Body Reinforcement I: +1/+1
Consume Toxin Rune, Body Reinforcement I Rune, Venom

Swift-Sama:
Class
Craft King Rune as a bonus action
King: Train
King Rune: Bunker
Consume King Rune

TempelJaeger:
Shop for Automata (Do you have a source on that? Source? A source. I need a source. Sorry, I mean I need a source that explicitly states your argument. This is just tangential to the discussion. No, you can't make inferences and observations from the sources you've gathered. Any additional comments from you MUST be a subset of the information from the sources you've gathered. You can't make normative statements from empirical evidence. Do you have a degree in that field? A Polyhistor degree? In that field? Then your arguments are invalid. No, it doesn't matter how close those data points are correlated. Correlation does not equal causation. Correlation does not equal causation. CORRELATION. DOES. NOT. EQUAL. CAUSATION. You still haven't provided me a valid source yet. Nope, still haven't.), Cheat Sheet, Paperwork
Mental Fortification I
Resurrection
Scapegoat I: Anemone

Teyao:
Train
Attune to Water, Water, Gold
Consume Shrooms

Witherbrine:
Attack NinetyNineLies, DragonLord, Coledon
Bunker as a bonus action
Attune to Earth, Earth, Earth, Fire, Fire
Consume Fire I Rune
"""
def turn_13():
    anemone, _, black, cole, darklight, darkpip, dragon, drasky, _, hypo, _, mega, ninety, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_class()
    anemone.plan_trade(drasky, item_names=['Shrooms'])

    black.plan_train()
    black.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    black.plan_hydro('Body Reinforcement II', [0, 3], contingency=True)
    black.plan_hydro('Body Reinforcement III', [0, 5], contingency=True)
    black.plan_hydro('Unnatural Intuition', contingency=True)
    black.set_dev_plan('Awareness I', 'Aeromancy Intuition')

    cole.plan_nothing()

    darklight.plan_class()
    darklight.plan_hydro('Combat Regeneration (Hydro)', contingency=True)
    # darklight.plan_trade(dragon, 9) # bounced by Styx rule as they traded all of their credits.

    # Bounced by Styx rule as they shopped for all of their credits.
    # darkpip.plan_shop('Liquid Memories', 'Liquid Memories', 'Cheat Sheet', 'Paperwork')
    # darkpip.plan_attune(Element.GOLD, Element.EARTH)

    dragon.plan_class()

    drasky.plan_shop('Chronoshift Bomb', 'Shrooms')

    hypo.plan_shop('Chronoshift Bomb')
    hypo.plan_craft_rune('Toxin', bonus=True)
    hypo.plan_attune(Element.WATER, Element.FIRE)
    hypo.plan_trade(drasky, item_names=['Venom'])

    # Bounced by Styx rule as they shopped for all of their credits.
    # mega.plan_shop('Liquid Memories', 'Medkit', 'Caltrops', 'Venom')
    # mega.plan_attune(Element.EARTH, Element.WATER, Element.AIR)

    ninety.plan_shop('Liquid Memories', 'Cheat Sheet')
    ninety.plan_hydro('Unnatural Intuition', contingency=True)

    para.plan_class()
    para.plan_hydro('Mental Fortification II', will=[0, 2])
    para.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    para.plan_hydro('Body Reinforcement II', [0, 3], contingency=True)

    pocket.plan_shop('Lizard Tail', 'Lizard Tail', 'Lizard Tail', 'Ablative Ossification')
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')

    ryo.plan_shop('Chronoshift Bomb', 'Ablative Ossification')
    ryo.plan_attune(Element.WATER)

    seven.plan_attack(ryo)
    seven.plan_craft_rune('Body Reinforcement I', bonus=True)
    seven.plan_hydro('Body Reinforcement I', will=[1, 1])
    seven.plan_consume_item('Toxin Rune', 'Body Reinforcement I Rune', 'Venom')

    swift.plan_class()
    swift.plan_craft_rune('King', bonus=True)
    swift.plan_ability_choose('King', king_choice('Bunker'), for_rune=True)
    swift.plan_ability_choose('King', king_choice('Train'))
    swift.plan_consume_item('King Rune')
    swift.set_dev_plan('Quiet Attune', 'Circuit III')

    # Bounced by Styx rule as they shopped for all of their credits.
    # tempel.plan_shop('Automata', 'Cheat Sheet', 'Paperwork', automata_name=["Do you have a source on that? Source? A source. I need a source. Sorry, I mean I need a source that explicitly states your argument. This is just tangential to the discussion. No, you can't make inferences and observations from the sources you've gathered. Any additional comments from you MUST be a subset of the information from the sources you've gathered. You can't make normative statements from empirical evidence. Do you have a degree in that field? A Polyhistor degree? In that field? Then your arguments are invalid. No, it doesn't matter how close those data points are correlated. Correlation does not equal causation. Correlation does not equal causation. CORRELATION. DOES. NOT. EQUAL. CAUSATION. You still haven't provided me a valid source yet. Nope, still haven't."])
    # tempel.plan_hydro('Mental Fortification I')
    # tempel.plan_hydro('Resurrection')
    # tempel.plan_target('Scapegoat I', anemone)

    teyao.plan_train()
    teyao.plan_attune(Element.WATER, Element.WATER, Element.GOLD)   
    teyao.plan_consume_item('Shrooms')

    wither.plan_attack(ninety, dragon, cole)
    wither.plan_bunker(bonus=True)
    wither.plan_attune(Element.EARTH, Element.EARTH, Element.EARTH, Element.FIRE, Element.FIRE)
    wither.plan_consume_item('Fire I Rune')
    
    Action.run_turn(GAME)

"""
Anemone:
Bunker

BlackLemonAde:
Body Reinforcement I: +1/+1
Body Reinforcement II: +3 combat
Body Reinforcement III: +5 combat
Chaos: Drasky

DarkLight:
Attack Megaolix
Combat Regeneration (Hydro)

Darkpiplumon:
Bunker
Attune to Gold, Earth
Chameleon

DragonLord:
Attack Anemone

Drasky:
Attack Teyao
Attune to Earth
Consume Venom, Shrooms, Fire I Rune
Trade 1 credit to Seventeen

HypoSoc:
Attack Teyao
Craft Fire I Rune as a bonus action
Attune to Water, Fire, Anti
Consume Venom, Fire I Rune, Toxin Rune
Trade 1 credit to Seventeen

Megaolix:
Attack Witherbrine
Attune to Earth, Water, Air
Bounty: Drasky (6)
Bounty: HypoSoc (6)

Paradosi:
Train
Mental Fortification I
Body Reinforcement I: +1 surv (contingency)
Body Reinforcement II: +2 surv (contingency)
Arsonist: PocketRikimaru

PocketRikimaru:
Train
Attune to Gold
Mental Fortification I

RyoAtemi:
Bunker
Attune to Water

Seventeen:
Attack PocketRikimaru
Craft Martial Arts III Rune as a bonus action

Swift-Sama:
Train
Craft King Rune as a bonus action
Attune to Water, Water
King: Shop
King Rune: Class
Consume King Rune

TempelJaeger:
Attack Anemone
Mental Fortification I
Resurrection
Scapegoat I: Megaolix

TempelJaeger:
Heal RyoAtemi
Attune to Water, Water, Gold

Witherbrine:
Attack RyoAtemi, DarkLight, Anemone
Craft Fire II Rune as a bonus action
Attune to Earth, Earth, Earth, Fire, Anti
"""
def turn_14():
    anemone, _, black, _, darklight, darkpip, dragon, drasky, _, hypo, _, mega, _, para, pocket, ryo, seven, swift, tempel, teyao, wither = load_players()

    anemone.plan_bunker()

    black.plan_hydro('Body Reinforcement I', [1, 1])
    black.plan_hydro('Body Reinforcement II', [3, 0])
    black.plan_hydro('Body Reinforcement III', [5, 0])
    # black.plan_trade(drasky, 6, item_names=['Lizard Tail']) # bounced by Styx rule as they traded all of their credits.

    darklight.plan_attack(mega)
    darklight.plan_hydro('Combat Regeneration (Hydro)')

    darkpip.plan_bunker()
    darkpip.plan_attune(Element.GOLD, Element.EARTH)
    darkpip.plan_target('Chameleon', darkpip)

    dragon.plan_attack(anemone)

    drasky.plan_attack(teyao)
    drasky.plan_attune(Element.EARTH)
    drasky.plan_consume_item('Venom', 'Shrooms', 'Fire I Rune')
    drasky.plan_trade(seven, 1)
    drasky.set_dev_plan('Antimagic (Geo)', 'Antimagic (Hydro)')

    hypo.plan_attack(teyao)
    hypo.plan_craft_rune('Fire I', bonus=True)
    hypo.plan_attune(Element.WATER, Element.FIRE, Element.ANTI)
    hypo.plan_consume_item('Venom', 'Fire I Rune', 'Toxin Rune')
    hypo.plan_trade(seven, 1)

    # bounced by Styx rule as they used all of their credits for a bounty.
    # mega.plan_attack(wither)
    # mega.plan_attune(Element.EARTH, Element.WATER, Element.AIR)
    # mega.plan_bounty(drasky, 6)
    # mega.plan_bounty(hypo, 6)

    para.plan_train()
    para.plan_hydro('Mental Fortification I')
    para.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    para.plan_hydro('Body Reinforcement II', [0, 2], contingency=True)
    para.plan_target('Arsonist', pocket)

    pocket.plan_train()
    pocket.plan_attune(Element.GOLD)
    pocket.plan_hydro('Mental Fortification I')
    pocket.set_dev_plan('Body Reinforcement I')

    ryo.plan_bunker()
    ryo.plan_attune(Element.WATER)

    seven.plan_attack(pocket)
    seven.plan_craft_rune('Martial Arts III', bonus=True)

    swift.plan_train()
    swift.plan_craft_rune('King', bonus=True)
    swift.plan_attune(Element.WATER, Element.WATER)
    swift.plan_ability_choose('King', king_choice('Shop'), for_rune=True)
    swift.plan_ability_choose('King', king_choice('Class'))
    swift.plan_consume_item('King Rune')
    swift.set_dev_plan('Mental Fortification I', 'Mental Fortification II', 'Quiet Attune', 'Circuit III')

    tempel.plan_attack(anemone)
    tempel.plan_hydro('Mental Fortification I')
    tempel.plan_hydro('Resurrection')
    tempel.plan_target('Scapegoat I', mega)
    tempel.set_dev_plan('Mental Fortification II', 'Mental Fortification III', 'Willpower V', 'Soul Strike', 'Scapegoat II', 'Body Reinforcement I', 'Speed (Hydro) I', 'Speed (Hydro) II', 'Willpower Draining', 'Scapegoat III', 'Scapegoat IV', 'Augur II', 'Augur III', 'Augur IV')

    teyao.plan_heal(ryo)
    teyao.plan_attune(Element.WATER, Element.WATER, Element.GOLD)

    wither.plan_attack(ryo, darklight, anemone)
    wither.plan_craft_rune('Fire II', bonus=True)
    wither.plan_attune(Element.EARTH, Element.EARTH, Element.EARTH, Element.FIRE, Element.ANTI)
    wither.set_dev_plan('Hell Fire', 'Circuit VI', 'Petrification I', 'Martial Arts I', 'Martial Arts II', 'Martial Arts III')

    Action.run_turn(GAME)

"""
Anemone:
Shop for Chronoshift Bomb
Attune to Warp
Warp: Witherbrine

BlackLemonAde:
Shop for Chronoshift Bomb
Body Reinforcement II: +2 surv (contingency)
Body Reinforcement III: +5 surv (contingency)

Darkpiplumon:
Shop for Liquid Memories, Liquid Memories, Cheat Sheet, Paperwork
Attune to Gold, Earth

DragonLord:
Shop for Oblivion Ordinance, Camo Cloak, Venom

Drasky:
Bunker
Attune to Earth, Anti
Consume Shrooms

HypoSoc:
Class
Craft Toxin Rune as a bonus action
Consume Venom

Paradosi:
Shop for Force Projection, Cheat Sheet, Booby Trap, Venom
Mental Fortification I
Mental Fortification II: +1 progress
Body Reinforcement I: +1 surv (contingency)
Body Reinforcement II: +1 surv (contingency)

PocketRikimaru:
Class
Mental Fortification I

RyoAtemi:
Shop for Chronoshift Bomb
Attune to Water
Trade Chronoshift Bomb to Swift-Sama

Seventeen:

Swift-Sama:
Class
Craft King Rune as a bonus action
King: Train
King Rune: Bunker
Consume King Rune

TempelJaeger:
Class
Mental Fortification II: +1 Academics
Mental Fortification III: +1 Academics
Resurrection
Scapegoat I: Swift-Sama

Witherbrine:
Attack RyoAtemi, HypoSoc, Anemone
Craft Hell Fire Rune as a bonus action
Attune to Earth, Earth, Earth, Fire, Fire, Anti
Fire II Rune: Consume
"""
def turn_15():
    anemone, _, black, _, _, darkpip, dragon, drasky, _, hypo, _, _, _, para, pocket, ryo, seven, swift, tempel, _, wither = load_players()

    anemone.plan_shop('Chronoshift Bomb')
    anemone.plan_attune(Element.WARP)
    anemone.plan_target('Warp', wither)

    # controlled by Drasky
    black.plan_shop('Chronoshift Bomb')
    black.plan_hydro('Body Reinforcement II', [0, 2], contingency=True)
    black.plan_hydro('Body Reinforcement III', [0, 5], contingency=True)

    darkpip.plan_shop('Liquid Memories', 'Liquid Memories', 'Cheat Sheet', 'Paperwork')
    darkpip.plan_attune(Element.GOLD, Element.EARTH)

    # bounced by Styx rule as they traded all of their credits.
    # dragon.plan_shop('Oblivion Ordinance', 'Camo Cloak', 'Venom')

    # controlled by BlackLemonAde
    drasky.plan_bunker()
    drasky.plan_attune(Element.EARTH, Element.ANTI)
    drasky.plan_consume_item('Shrooms')
    drasky.set_dev_plan('Antimagic (hydro)', 'Martial arts III', 'Awareness I')

    hypo.plan_class()
    hypo.plan_craft_rune('Toxin', bonus=True)
    hypo.plan_consume_item('Venom')

    # bounced by Styx rule as they shopped for all of their credits.
    # para.plan_shop('Force Projection', 'Cheat Sheet', 'Booby Trap', 'Venom')
    # para.plan_hydro('Mental Fortification I')
    # para.plan_hydro('Mental Fortification II', will=[1, 0])
    # para.plan_hydro('Body Reinforcement I', [0, 1], contingency=True)
    # para.plan_hydro('Body Reinforcement II', [0, 1], contingency=True)

    pocket.plan_class()
    pocket.plan_hydro('Mental Fortification I')

    ryo.plan_shop('Chronoshift Bomb')
    ryo.plan_attune(Element.WATER)
    ryo.plan_trade(swift, item_names=['Chronoshift Bomb'])

    seven

    swift.plan_class()
    swift.plan_craft_rune('King', bonus=True)
    swift.plan_ability_choose('King', king_choice('Train'), for_rune=True)
    swift.plan_ability_choose('King', king_choice('Bunker'))
    swift.plan_consume_item('King Rune')

    tempel.plan_class()
    tempel.plan_hydro('Mental Fortification II', will=[0, 2])
    tempel.plan_hydro('Mental Fortification III', will=[0, 1])
    tempel.plan_hydro('Resurrection')
    tempel.plan_target('Scapegoat I', swift)

    wither.plan_attack(ryo, hypo, anemone)
    wither.plan_craft_rune('Hell Fire', bonus=True)
    wither.plan_attune(Element.EARTH, Element.EARTH, Element.EARTH, Element.FIRE, Element.FIRE, Element.ANTI)
    wither.plan_consume_item('Fire II Rune')
    wither.set_dev_plan('Petrification I','Antimagic (Aero)', 'Antimagic (Geo)')

    Action.run_turn(GAME)

if __name__ == '__main__':
    init()
    turn_1()
    turn_2()
    turn_3()
    turn_4()
    turn_5()
    turn_6()
    turn_7()
    statuses = turn_8()
    turn_9(statuses)
    turn_10()
    turn_11()
    turn_12()
    turn_13()
    turn_14()
    turn_15()
    report(leaderboard_report=True, leaderboard_academics=False, summary_report=True, player_reports=True)