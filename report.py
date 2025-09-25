import os
from typing import NoReturn, TYPE_CHECKING, Callable, Any, Dict, Optional, Tuple, List, Set

from ability import get_ability
from combat import get_combat_handler
from constants import InfoScope, Element, Condition
from game import Game

if TYPE_CHECKING:
    from automata import Automata
    from player import Player
    from items import Item

ReportCallable = Callable[[str, InfoScope], Any]


def int_to_roman(i):
    return ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"][i]


class Report(object):
    MAIN_REPORT: 'Report' = None

    def __init__(self):
        self.actions: List[Tuple['Player', str, bool, bool, Optional['Player']]] = []
        self.broadcast_events: List[Tuple[str, bool]] = []
        self.aero_broadcast: bool = False
        self.dead: Set['Player'] = set()
        self.petrified: Set['Player'] = set()
        self.face_mask: Dict[str, str] = {}
        self.training: Dict['Player', str] = {}
        self.circuits: Dict['Player', Tuple[Element, ...]] = {}
        self.willpower: Dict['Player', int] = {}
        self.shop: List[Tuple['Player', int, Dict['Item', int], List[str]]] = []
        self.trades: List[Tuple['Player', 'Player', int, Dict['Item', int], List['Automata']]] = []
        self.bounties: List[Tuple['Player', 'Player', int]] = []
        self.hiding: Set['Player'] = set()
        self.messages: List[Tuple['Player', List['Player'], str]] = []

    def reset(self):
        self.actions.clear()
        self.broadcast_events.clear()
        self.aero_broadcast = False
        self.dead.clear()
        self.petrified.clear()
        self.face_mask.clear()
        self.training.clear()
        self.circuits.clear()
        self.willpower.clear()
        self.shop.clear()
        self.trades.clear()
        self.bounties.clear()
        self.hiding.clear()
        self.messages.clear()

    def add_action(self, player: "Player", content: str,
                   fake: bool = False, hidden: bool = False,
                   aero: Optional['Player'] = None) -> NoReturn:
        if player not in self.hiding:
            self.actions.append((player, content, fake, hidden, aero))
        else:
            self.actions.append((player, content, fake, True, aero))

    def add_action_if_not_duplicate(self, player: "Player", content: str,
                   fake: bool = False, hidden: bool = False,
                   aero: Optional['Player'] = None) -> NoReturn:
        if (player, content, fake, hidden, aero) not in self.actions:
            self.add_action(player, content, fake, hidden, aero)

    def add_petrification(self, player: "Player"):
        if player not in self.petrified:
            self.petrified.add(player)

    def add_death(self, player: "Player"):
        if player not in self.dead:
            self.dead.add(player)

    def set_attunement(self, player: "Player", elements: Tuple[Element, ...]):
        self.circuits[player] = elements

    def spend_willpower(self, player: "Player", will: int):
        if will <= 0:
            return
        if player not in self.willpower:
            self.willpower[player] = 0
        self.willpower[player] += will

    def add_shop(self, player: "Player", money: int, items: Dict["Item", int], automata_names: List['str']):
        self.shop.append((player, money, items, automata_names))

    def add_trade(self, player: "Player", target: "Player", money: int,
                  items: Dict["Item", int], automata: List['Automata']):
        self.trades.append((player, target, money, items, automata))

    def add_bounty(self, player: "Player", target: "Player", money: int):
        self.bounties.append((player, target, money))

    def broadcast(self, content: str, intuition_required: bool = False) -> NoReturn:
        self.broadcast_events.append((content, intuition_required))
        if intuition_required:
            self.aero_broadcast = True

    def set_training(self, player: 'Player', ability: str):
        self.training[player] = ability

    def mark_hiding(self, player: 'Player'):
        self.hiding.add(player)

    def mark_revealed(self, player: 'Player'):
        self.hiding.discard(player)

    def apply_face_mask(self, user_name: str, target_name: str):
        self.face_mask[user_name] = target_name

    def add_message(self, origin: 'Player', destination: List['Player'], msg: str):
        self.messages.append((origin, destination, msg))

    def face_mask_replacement(self, message: str, player_name=""):
        # Make sure to use this line by line so the mask donning doesn't interfere
        if 'donned a mask' in message:
            return message

        masked = message

        for masker in self.face_mask:
            masked = masked.replace(masker, f"__{masker}__")

        for masker in self.face_mask:
            if masker != player_name:
                if self.face_mask[masker] == player_name:
                    masked = masked.replace(f"__{masker}__", "someone wearing your face")
                else:
                    masked = masked.replace(f"__{masker}__", self.face_mask[masker])

        for masker in self.face_mask:
            masked = masked.replace(f"__{masker}__", masker)

        return masked

    def get_combat_report_for_player(self, player: 'Player'):
        return self.face_mask_replacement(get_combat_handler().get_combat_report_for_player(player),
                                          player_name=player.name)

    def get_night_combat_report(self, player: 'Player', intuition=False):
        return self.face_mask_replacement(get_combat_handler()
                                          .get_public_combat_report(intuition, ignore_player=player), player.name)

    def get_spy_report(self, spy: 'Player', target: 'Player', counter_int: bool = False):
        fake_ability_str = "nothing"
        if target.fake_ability:
            fake_ability_str = target.fake_ability.name
        report = ""

        if (target.is_dead() and target not in self.dead) or \
                (target.has_condition(Condition.HIDING) and counter_int
                 and not target.has_condition(Condition.FRESH_HIDING)):
            report += f"{target.name} is dead." + os.linesep + os.linesep

        else:
            if target.has_condition(Condition.HIDING):
                report += f"You discovered that {target.name} is actually alive." + os.linesep + os.linesep

            if counter_int:
                report += target.fake_action.public_description + os.linesep
            else:
                for (player, content, fake, hidden, aero) in self.actions:
                    if player.name == target.name and not hidden:
                        if not aero or spy.has_condition(Condition.INTUITION):
                            report += self.face_mask_replacement(content, spy.name) + os.linesep

            # Normally you see night combat with Awareness I, so it is redundant to include
            # But there are potential edge cases with Runes, and Network Spike
            if not spy.has_ability("Awareness I") and not counter_int:
                report += os.linesep
                report += self.face_mask_replacement(get_combat_handler()
                                                     .get_combat_report_for_player_as_observer(target, spy),
                                                     player_name=spy.name)

            if spy.has_ability("Awareness II"):
                if counter_int:
                    if type(target.fake_action).__name__ in ['Train', 'Class']:
                        report += os.linesep
                        report += f"{target.name} was training {fake_ability_str}."
                elif target in self.training:
                    report += os.linesep
                    report += f"{target.name} was training {self.training[target]}."

            if spy.has_ability("Trade Secrets"):
                if counter_int:
                    report += os.linesep
                    if target.fake_ability:
                        report += f"{target.name} seems to be working on {fake_ability_str}."
                    else:
                        report += f"{target.name} is not working on anything."
                else:
                    report += os.linesep
                    if target.dev_plan:
                        ability_name = get_ability(target.dev_plan[0]).name
                        if target.dev_plan[0] >= 700:
                            ability_name = 'Concept ' + int_to_roman((target.dev_plan[0] % 100))
                        report += f"{target.name} seems to be working on {ability_name}."
                    else:
                        report += f"{target.name} is not working on anything."

            if spy.has_ability("Profiling"):
                temperament = target.get_temperament_display()
                if counter_int:
                    temperament = target.get_fake_temperament()
                report += f"{target.name} appears to have a {temperament} temperament."

        return report

    def get_attunement_report(self, perspective_player: Optional['Player']) -> str:
        report = ""
        unsorted = []
        perspective_name = ""
        if perspective_player:
            perspective_name = perspective_player.name
        for player, circuits in self.circuits.items():
            if circuits:
                unsorted.append(self.face_mask_replacement(f"{player.name} attuned to "
                                                           f"{'/'.join([circuit.name for circuit in circuits])}.",
                                                           perspective_name))
        report += os.linesep.join(sorted(unsorted))
        if not report:
            report = "You detected no Geomancy."
        return report + os.linesep

    def get_willpower_report(self, perspective_player: Optional['Player']) -> str:
        report = ""
        unsorted = []
        perspective_name = ""
        if perspective_player:
            perspective_name = perspective_player.name
        for player, amount in self.willpower.items():
            unsorted.append(self.face_mask_replacement(f"{player.name} spent {amount} willpower.", perspective_name))
        report += os.linesep.join(sorted(unsorted))
        if not report:
            report = "You detected no Willpower."
        return report + os.linesep

    def get_money_report(self, full=False, perspective_player: Optional['Player']=None) -> str:
        report = ""
        perspective_name = ""
        if perspective_player:
            perspective_name = perspective_player.name

        for player, money, items, automata_names in sorted(self.shop, key=lambda x: x[0].name):
            plural = '' if money == 1 else 's'
            report += f"{player.name} spent {money} credit{plural} at Shop Club." + os.linesep
            if full:
                for item, amount in items.items():
                    report += f"-- {item.name} x{amount}" + os.linesep
                if automata_names:
                    for automaton_name in automata_names:
                        report += f"-- {automaton_name}" + os.linesep
        if report:
            report += os.linesep

        unsorted = []
        for player, target, money, items, automata in self.trades:
            mini_report = f"{self.face_mask_replacement(player.name, perspective_name)} traded with {target.name}." \
                          + os.linesep
            if full:
                if money:
                    plural = "credit"
                    if money > 1:
                        plural = "credits"
                    mini_report += f"-- {money} {plural}." + os.linesep
                if items:
                    for item, amount in items.items():
                        mini_report += f"-- {item.name} x{amount}" + os.linesep
                if automata:
                    for automaton in automata:
                        mini_report += f"-- {automaton.name}" + os.linesep
            unsorted.append(mini_report)
        report += os.linesep.join(sorted(unsorted))

        if report:
            report += os.linesep
        if full:
            unsorted = []
            for player, target, money in self.bounties:
                unsorted.append(f"{self.face_mask_replacement(player.name, perspective_name)} placed a {money} "
                                f"credit bounty on {target.name}.")
            report += os.linesep.join(sorted(unsorted))
        if report:
            report += os.linesep
        else:
            report += "No trades happened." + os.linesep
        return os.linesep + report

    def get_action_report(self, pierce_illusions=False, ignore_player: Optional['Player'] = None,
                          intuition: bool = False, aero_only: bool = False) -> str:
        report = ""
        for (player, content, fake, hidden, aero) in sorted(self.actions,
                                                            key=lambda x: (x[4] is None, x[0].name.upper())):
            if not ignore_player or ignore_player.name != player.name:
                if not hidden or pierce_illusions:
                    if not pierce_illusions or not fake:
                        if not aero_only or aero:
                            report += content + os.linesep
                            if aero and intuition:
                                assert aero.concept
                                report += f"Your intuition tells you " \
                                          f"this has to do with the concept {aero.concept}." + os.linesep
        return report

    def get_personal_action_report(self, pierce_illusions=False, ignore_player: Optional['Player'] = None,
                                   intuition: bool = False) -> str:
        report = ""
        player_set = set()
        for (player, content, fake, hidden, aero) in sorted(self.actions,
                                                            key=lambda x: (x[4] is None, x[0].name.upper())):
            if not ignore_player or ignore_player.name != player.name:
                if not pierce_illusions and player.has_ability("Counter Intelligence I"):
                    if player not in player_set:
                        player_set.add(player)
                        report += player.fake_action.public_description + os.linesep
                elif not hidden or pierce_illusions:
                    if not pierce_illusions or not fake:
                        report += content + os.linesep
                        if aero and intuition:
                            assert aero.concept
                            report += f"Your intuition tells you " \
                                      f"this has to do with the concept {aero.concept}." + os.linesep
        return report

    def get_broadcasts(self, intuition: bool, skip_combat: bool = False):
        report = ""
        for event, intuition_required in self.broadcast_events:
            if intuition or not intuition_required:
                report += self.face_mask_replacement(event) + os.linesep
        if not skip_combat:
            for event, intuition_required in get_combat_handler().broadcast_events:
                if intuition or not intuition_required:
                    report += self.face_mask_replacement(event) + os.linesep
        return report

    def generate_report(self, game: Game):
        report = str(game) + os.linesep
        report += self.get_broadcasts(intuition=False) + os.linesep

        for player, amt in sorted(set([(target, amount) for (_, target, amount) in self.bounties])):
            report += f"A {amt} credit bounty was placed on {player.name} ({player.bounty} total)." + os.linesep + os.linesep

        if game.is_day():
            report += get_combat_handler().get_public_combat_report()
            report += os.linesep
            report += self.get_action_report()
            report += os.linesep

            for (player, verb) in get_combat_handler().verb_dict.items():
                report = report.replace(f"{player.name} attacked", f"{player.name} {verb}")

        return report

    @staticmethod
    def player_list_to_string(players: List['Player']) -> str:
        assert len(players)
        temp = sorted([p.name for p in players])
        if len(temp) == 1:
            return temp[0]
        if len(temp) == 2:
            return f'{temp[0]} and {temp[1]}'
        return f'{", ".join(temp[:-1])}, and {temp[-1]}'

    def get_messages_for_player(self, player: 'Player'):
        outbox: List[Tuple[str, str]] = []
        inbox: List[Tuple[str, str, str]] = []
        for origin, destination, msg in self.messages:
            if origin.name == player.name:
                outbox.append((Report.player_list_to_string(destination), msg))
            elif player.has_ability("Panopticon"):
                inbox.append((origin.name, Report.player_list_to_string(destination), msg))
            elif player.name in [d.name for d in destination]:
                inbox.append((self.face_mask_replacement(origin.name), Report.player_list_to_string(destination), msg))
        box = ""
        if outbox:
            box += "Outbox:" + os.linesep
            for destination, msg in sorted(outbox):
                box += f'FROM {self.face_mask_replacement(player.name)}'
                box += f' TO {destination}:' + os.linesep
                box += msg + os.linesep + os.linesep
        if inbox:
            box += "Inbox:" + os.linesep
            for origin, destination, msg in sorted(inbox):
                box += f'FROM {origin}'
                box += f' TO {destination}:' + os.linesep
                box += msg + os.linesep + os.linesep
        return box


def get_main_report():
    if Report.MAIN_REPORT is None:
        Report.MAIN_REPORT = Report()
    return Report.MAIN_REPORT
