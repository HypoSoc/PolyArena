import json
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
        self.automata: Dict[str, 'Player'] = {}

    def __str__(self):
        time_of_day = "Day"
        if self.night:
            time_of_day = "Night"
        return f"{time_of_day} {self.turn}"

    def to_file_suffix(self):
        time_of_day = "d"
        if self.night:
            time_of_day = "n"
        return f"{self.turn}{time_of_day}"

    def clone(self, complete: bool = False):
        clone = Game()
        clone.turn = self.turn
        clone.night = self.night
        clone.events = []  # Todo if serializing
        clone.simulation = True

        if complete:
            clone.players = {c.name: c for c in [p.make_copy_for_simulation(clone) for p in self.players.values()]}

        return clone

    def serialize(self) -> Dict:
        turn = {'turn': self.turn, 'night': self.night,
                'remaining': [player.name for player in self.players.values() if not player.is_dead()],
                'events': self.events,
                'players': {player_name: player.serialize() for (player_name, player) in self.players.items()},
                'automata': {automata_name: automata.serialize() for (automata_name, automata) in
                             self.automata.items() if not automata.is_dead()}}
        return turn

    def save(self, file_prefix: str, permit_sim: bool = False):
        if not permit_sim:
            assert not self.simulation

        serialized = self.serialize()

        with open(f"save/{file_prefix}_{self.to_file_suffix().replace(' ', '_').lower()}.json", 'w') as f:
            json.dump(serialized, f, indent=4)

        with open(f"save/{file_prefix}.json", 'w') as f:
            json.dump(serialized, f, indent=4)

    def get_player(self, name: str):
        if name in self.players:
            return self.players[name]
        if name in self.automata:
            return self.automata[name]
        raise Exception(f"Unknown player {name}.")

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
                    source_player = self.get_player(source)
                    target_players = [self.get_player(target)
                                      for target in targets if not self.get_player(target).is_dead()]
                    if not source_player.is_dead():
                        from actions import HandleSkill
                        skill = get_skill(skill_pin)
                        skill.targets = target_players
                        HandleSkill.handle_noncombat_skill(self, source_player, skill)
                    handled.append((turn, night, skill_pin, source, targets))
        for handled_event in handled:
            self.events.remove(handled_event)

    def is_day(self):
        return not self.night

    def is_night(self):
        return self.night

    def add_event_in_x_turns(self, turns: int, skill_pin: int,
                             source: 'Player', targets: Optional[List['Player']] = None):
        assert turns > 0
        turn = self.turn
        night = self.night
        while turns > 0:
            turns -= 1
            if night:
                turn += 1
            night = not night
        self.add_event(turn, night, skill_pin, source, targets)

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
        name_list = list(self.players.keys()) + list(self.automata.keys())
        for name in name_list:
            if name in player.name:
                raise Exception(f"{player.name} is a superstring of {name}!")
            if player.name in name:
                raise Exception(f"{player.name} is a substring of {name}!")

        if type(player).__name__ == 'Automata':
            self.automata[player.name] = player
        else:
            self.players[player.name] = player
