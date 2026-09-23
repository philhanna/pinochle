# pinochle.ports.admin_port
from abc import ABC, abstractmethod

from pinochle.domain.player import Player
from pinochle.domain.team import Team


class AdminPort(ABC):
    """Primary port defining the administrative use cases for game setup.

    Provides the operations needed to configure a game before play begins:
    creating the game record, registering players and team assignments, and
    transitioning to dealer selection once all four players are seated — plus
    the two an administrator needs once it has begun: seating a computer in
    place of a player who has left (RT-12a), and ending a game that cannot be
    finished at all (RT-12).
    """

    @abstractmethod
    def create_game(self) -> str:
        """Create a new game and return its ID."""

    @abstractmethod
    def add_player(self, game_id: str, player: Player) -> None:
        """Register a player (human or computer) into the pending game."""

    @abstractmethod
    def assign_teams(self, game_id: str, ns: Team, ew: Team) -> None:
        """Assign the two partnerships."""

    @abstractmethod
    def start_game(self, game_id: str) -> None:
        """Shuffle the deck and begin dealer selection."""

    @abstractmethod
    def seat_computer(self, game_id: str, player_id: str) -> None:
        """Put a computer in the seat of a player who has gone (RT-12a)."""

    @abstractmethod
    def abandon_game(self, game_id: str) -> None:
        """Mark a game finished before it could be completed normally (RT-12)."""
