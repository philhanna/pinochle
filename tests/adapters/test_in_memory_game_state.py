# tests.adapters.test_in_memory_game_state
import pytest

from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.domain.game import Game
from tests.ports.test_game_state_port import run_contract


def test_contract():
    """Verify the adapter satisfies the shared game-state contract."""
    run_contract(InMemoryGameState())


def test_overwrite_existing_game():
    """Saving the same game id twice should replace the stored entry cleanly."""
    store = InMemoryGameState()
    g = Game("g1")
    store.save(g)
    store.save(g)  # second save must not raise
    assert store.load("g1") is g


def test_load_missing_raises():
    """Loading an unknown game id should raise ``KeyError``."""
    store = InMemoryGameState()
    with pytest.raises(KeyError):
        store.load("missing")
