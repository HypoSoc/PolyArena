from typing import Callable, Tuple, List, TYPE_CHECKING

if TYPE_CHECKING:
    from player import Player


class Game:
    def __init__(self, turn=1, night=False):
        # Sets turn to one before provided, with the expectation that advance happens first
        self.turn = turn
        if not night:
            self.turn -= 1
        self.night = not night
        self.events: List[Tuple[int, bool, Callable]] = []
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

        handled = []
        for turn, night, event in self.events:
            if turn == self.turn:
                if night == self.night:
                    event()
                    handled.append((turn, night, event))
        for handled_event in handled:
            self.events.remove(handled_event)

    def is_day(self):
        return not self.night

    def add_event(self, turn: int, night: bool, event: Callable):
        if turn < self.turn:
            return
        if turn == self.turn and (self.night or not night):
            return
        self.events.append((turn, night, event))

    def register(self, player: 'Player'):
        assert player.name not in self.players
        self.players[player.name] = player
