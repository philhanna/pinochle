# pinochle.adapters.in_memory_game_state
from pinochle.domain.game import Game
from pinochle.ports.game_state_port import GameStatePort


class InMemoryGameState(GameStatePort):
    """GameStatePort backed by a plain dict — suitable for dev and tests."""

    def __init__(self):
        """Initialize the in-memory storage dictionary."""
        self._store: dict[str, Game] = {}

    def save(self, game: Game) -> None:
        """Store or replace the persisted state for ``game.id``."""
        self._store[game.id] = game

    def load(self, game_id: str) -> Game:
        """Return the stored game for ``game_id`` or raise ``KeyError``."""
        if game_id not in self._store:
            raise KeyError(game_id)
        return self._store[game_id]

    def delete(self, game_id: str) -> None:
        """Remove the stored game entry identified by ``game_id``."""
        if game_id not in self._store:
            raise KeyError(game_id)
        del self._store[game_id]
