# pinochle.adapters.in_memory_game_state
from pinochle.domain.errors import UnknownGameError
from pinochle.domain.game import Game
from pinochle.ports.game_state_port import GameStatePort


class InMemoryGameState(GameStatePort):
    """``GameStatePort`` backed by a plain in-memory ``dict``.

    Suitable for unit tests, integration tests, and single-process development
    sessions where durability is not required.  State is lost when the process
    exits.  No serialization or copying is performed, so all callers share the
    same object reference for a given game id.
    """

    def __init__(self):
        """Initialize the in-memory storage dictionary."""
        self._store: dict[str, Game] = {}

    def save(self, game: Game) -> None:
        """Store or replace the persisted state for ``game.id``."""
        self._store[game.id] = game

    def load(self, game_id: str) -> Game:
        """Return the stored game for ``game_id`` or raise ``UnknownGameError``."""
        if game_id not in self._store:
            raise UnknownGameError(game_id)
        return self._store[game_id]

    def delete(self, game_id: str) -> None:
        """Remove the stored game entry identified by ``game_id``."""
        if game_id not in self._store:
            raise UnknownGameError(game_id)
        del self._store[game_id]
