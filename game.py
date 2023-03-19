from typing import Callable, Tuple, List


# TODO Serialize events
class Game:
    def __init__(self, turn=1, night=False):
        # Sets turn to one before provided, with the expectation that advance happens first
        self.turn = turn
        if not night:
            self.turn -= 1
        self.night = not night
        self.events: List[Tuple[int, bool, Callable]] = []
        self.simulation = False

    def __str__(self):
        time_of_day = "Day"
        if self.night:
            time_of_day = "Night"
        return f"{time_of_day} {self.turn}"

    def clone(self):
        clone = Game()
        clone.turn = self.turn
        clone.night = self.night
        clone.events = []  # Todo if serializing
        clone.simulation = True
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
