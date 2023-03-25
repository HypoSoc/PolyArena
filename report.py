import os
from typing import NoReturn, TYPE_CHECKING, Callable, Any, Dict, Optional, Tuple

from ability import get_ability
from combat import get_combat_handler
from constants import InfoScope, Element, Condition
from game import Game

if TYPE_CHECKING:
    from player import Player
    from items import Item

ReportCallable = Callable[[str, InfoScope], Any]


class DayReport(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(DayReport, cls).__new__(cls)
            cls.instance.actions = []
            cls.instance.broadcast_events = []
            cls.instance.dead = set()
            cls.instance.petrified = set()
            cls.instance.face_mask = {}
            cls.instance.training = {}
            cls.instance.circuits = {}  # Player to list of circuits
            cls.instance.willpower = {}  # Player to int
            cls.instance.shop = []  # List of (player, credits, items)
            cls.instance.trades = []  # List of (player, target, credits, items)
            cls.instance.bounties = []  # List of (player, target, credits)
            cls.instance.hiding = set()  # Set[Players]
        return cls.instance

    def reset(self):
        self.actions.clear()
        self.broadcast_events.clear()
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

    def add_action(self, player: "Player", content: str) -> NoReturn:
        if player not in self.hiding:
            self.actions.append((player, content))

    def add_petrification(self, player: "Player"):
        if player not in self.petrified:
            self.petrified.add(player)
            self.actions.append((player, f"{player.name} was Petrified."))

    def add_death(self, player: "Player"):
        if player not in self.dead:
            self.dead.add(player)

    def set_attunement(self, player: "Player", elements: Tuple[Element]):
        self.circuits[player] = elements

    def spend_willpower(self, player: "Player", will: int):
        if will <= 0:
            return
        if player not in self.willpower:
            self.willpower[player] = 0
        self.willpower[player] += will

    def add_shop(self, player: "Player", money: int, items: Dict["Item", int]):
        self.shop.append((player, money, items))

    def add_trade(self, player: "Player", target: "Player", money: int, items: Dict["Item", int]):
        self.trades.append((player, target, money, items))

    def add_bounty(self, player: "Player", target: "Player", money: int):
        # TODO Bounties
        self.bounties.append((player, target, money))

    def broadcast(self, content: str) -> NoReturn:
        self.broadcast_events.append(content)

    def set_training(self, player: 'Player', ability: str):
        self.training[player] = ability

    def mark_hiding(self, player: 'Player'):
        self.hiding.add(player)

    def mark_revealed(self, player: 'Player'):
        self.hiding.discard(player)

    def apply_face_mask(self, user_name: str, target_name: str):
        self.face_mask[user_name] = target_name

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

    def get_night_combat_report(self, player_name=""):
        return self.face_mask_replacement(get_combat_handler().get_public_combat_report(), player_name)

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
                report += target.fake_action.public_description
            else:
                for (player, content) in self.actions:
                    if player.name == target.name:
                        report += self.face_mask_replacement(content, spy.name) + os.linesep

            # Normally you see night combat with Awareness I, so it is redundant to include
            # But there are potential edge cases with Runes
            if not spy.has_ability("Awareness I") and not counter_int:
                report += os.linesep
                report += self.face_mask_replacement(get_combat_handler().get_combat_report_for_player(target),
                                                     player_name=spy.name)

            if spy.has_ability("Awareness II"):
                if counter_int:
                    if type(target.fake_action).__name__ == 'Train':
                        report += os.linesep
                        report += f"{target.name} was training {fake_ability_str}."
                elif target in self.training:
                    report += os.linesep
                    report += f"{target.name} was training {self.training[target]}."

            if spy.has_ability("Trade Secrets"):
                if counter_int and type(target.fake_action).__name__ != 'Train':
                    report += os.linesep
                    if target.fake_ability:
                        report += f"{target.name} seems to be working on {fake_ability_str}."
                    else:
                        report += f"{target.name} is not working on anything."
                elif target not in self.training:
                    report += os.linesep
                    if target.dev_plan:
                        report += f"{target.name} seems to be working on {get_ability(target.dev_plan[0]).name}."
                    else:
                        report += f"{target.name} is not working on anything."

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

    def get_money_report(self, full=False) -> str:
        report = ""
        for player, money, items in self.shop:
            report += f"{player.name} spent {money} credits at Shop Club." + os.linesep
            if full:
                for item, amount in items.items():
                    report += f"-- {item.name} x{amount}" + os.linesep
        if report:
            report += os.linesep
        for player, target, money, items in self.trades:
            report += f"{player.name} traded with {target.name}." + os.linesep
            if full:
                if money:
                    plural = "credit"
                    if money > 1:
                        plural = "credits"
                    report += f"-- {money} {plural}." + os.linesep
                if items:
                    for item, amount in items.items():
                        report += f"-- {item.name} x{amount}" + os.linesep
        if report:
            report += os.linesep
        if full:
            for player, target, money in self.bounties:
                report += f"{player.name} place a {money} credit bounty on {target.name}." + os.linesep
        if report:
            report += os.linesep
        else:
            report += "No trades happened." + os.linesep
        return report

    def get_action_report(self, pierce_illusions=False, ignore_player: Optional['Player'] = None) -> str:
        report = ""
        for (player, content) in sorted(self.actions, key=lambda x: x[0].name):
            if not ignore_player or ignore_player.name != player.name:
                report += content + os.linesep
        return report

    def generate_report(self, game: Game):
        report = str(game) + os.linesep
        if game.is_day():
            report += get_combat_handler().get_public_combat_report()
            report += os.linesep
            report += self.get_action_report()
            report += os.linesep

            for (player, verb) in get_combat_handler().verb_dict.items():
                report = report.replace(f"{player.name} attacked", f"{player.name} {verb}")

        for event in get_combat_handler().broadcast_events:
            report += self.face_mask_replacement(event) + os.linesep
        for event in self.broadcast_events:
            report += self.face_mask_replacement(event) + os.linesep
        return report
