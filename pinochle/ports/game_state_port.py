# pinochle.ports.game_state_port
from abc import ABC, abstractmethod

from pinochle.domain.game import Game


class GameStatePort(ABC):
    """Secondary port defining the persistence contract for ``Game`` aggregates.

    Implementations may back this with an in-memory dict (for tests), a
    relational database, a document store, or any other durable mechanism.
    The application core depends only on this interface, keeping persistence
    technology swappable without modifying domain or service code.
    """

    @abstractmethod
    def save(self, game: Game) -> None:
        """Persist the current game state."""

    @abstractmethod
    def load(self, game_id: str) -> Game:
        """Load and return the game with the given ID.

        Raises UnknownGameError if game_id is not found.
        """

    @abstractmethod
    def delete(self, game_id: str) -> None:
        """Remove a game from storage.

        Raises UnknownGameError if game_id is not found.
        """
