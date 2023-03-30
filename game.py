from typing import Tuple, List, TYPE_CHECKING, Dict, Optional

from skill import get_skill

if TYPE_CHECKING:
    from player import Player


class Game:
    def __init__(self, turn=1, night=False):
        # Sets turn to one before provided, with the expectation that advance happens first
        self.turn = turn
        if not night:
            self.turn -= 1
        self.night = not night
        # Turn, Night, Skill Pin, Source player name, target names
        self.events: List[Tuple[int, bool, int, str, List[str]]] = []
        self.simulation = False

        self.players: Dict[str, 'Player'] = {}

    def __str__(self):
        time_of_day = "Day"
        if self.night:
            time_of_day = "Night"
        return f"{time_of_day} {self.turn}"

    def clone(self, complete: bool = False):
        clone = Game()
        clone.turn = self.turn
        clone.night = self.night
        clone.events = []  # Todo if serializing
        clone.simulation = True

        if complete:
            clone.players = {c.name: c for c in [p.make_copy_for_simulation(clone) for p in self.players.values()]}

        return clone

    def advance(self):
        if self.night:
            self.night = False
            self.turn += 1
        else:
            self.night = True

        handled: List[Tuple[int, bool, int, str, List[str]]] = []
        for turn, night, skill_pin, source, targets in self.events:
            if turn == self.turn:
                if night == self.night:
                    source_player = self.players[source]
                    target_players = [self.players[target] for target in targets if not self.players[target].is_dead()]
                    if not source_player.is_dead():
                        from actions import HandleSkill
                        HandleSkill(self, source_player, get_skill(skill_pin),
                                    target_players if target_players else None)
                    handled.append((turn, night, skill_pin, source, targets))
        for handled_event in handled:
            self.events.remove(handled_event)

    def is_day(self):
        return not self.night

    def add_event(self, turn: int, night: bool, skill_pin: int,
                  source: 'Player', targets: Optional[List['Player']] = None):
        if not targets:
            targets = []
        if turn < self.turn:
            return
        if turn == self.turn and (self.night or not night):
            return
        self.events.append((turn, night, skill_pin, source.name, [target.name for target in targets]))

    def register(self, player: 'Player'):
        assert player.name not in self.players
        self.players[player.name] = player
