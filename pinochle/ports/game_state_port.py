# pinochle.ports.game_state_port
from abc import ABC, abstractmethod

from pinochle.domain.game import Game


class GameStatePort(ABC):
    """Persistence interface for loading and saving game aggregates."""

    @abstractmethod
    def save(self, game: Game) -> None:
        """Persist the current game state."""

    @abstractmethod
    def load(self, game_id: str) -> Game:
        """Load and return the game with the given ID.

        Raises KeyError if game_id is not found.
        """

    @abstractmethod
    def delete(self, game_id: str) -> None:
        """Remove a game from storage.

        Raises KeyError if game_id is not found.
        """
