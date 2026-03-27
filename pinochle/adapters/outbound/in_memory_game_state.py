# pinochle.adapters.outbound.in_memory_game_state
from pinochle.domain.game import Game
from pinochle.ports.outbound.game_state_port import GameStatePort


class InMemoryGameState(GameStatePort):
    """GameStatePort backed by a plain dict — suitable for dev and tests."""

    def __init__(self):
        self._store: dict[str, Game] = {}

    def save(self, game: Game) -> None:
        self._store[game.id] = game

    def load(self, game_id: str) -> Game:
        if game_id not in self._store:
            raise KeyError(game_id)
        return self._store[game_id]

    def delete(self, game_id: str) -> None:
        if game_id not in self._store:
            raise KeyError(game_id)
        del self._store[game_id]
