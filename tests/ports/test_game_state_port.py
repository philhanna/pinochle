# tests.ports.test_game_state_port
"""Contract tests for GameStatePort.

Any concrete adapter must pass these tests.  Parametrize the `store`
fixture in conftest.py (or override it per adapter test module) to add
new implementations.
"""
import pytest

from pinochle.domain.game import Game
from pinochle.ports.game_state_port import GameStatePort


def run_contract(store: GameStatePort) -> None:
    """Assert the game-state adapter can save, load, and delete games."""
    game = Game("g1")

    store.save(game)
    loaded = store.load("g1")
    assert loaded.id == "g1"

    store.delete("g1")
    with pytest.raises(KeyError):
        store.load("g1")

    with pytest.raises(KeyError):
        store.delete("g1")
