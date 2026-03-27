# tests.adapters.test_in_memory_game_state
import pytest

from pinochle.adapters.outbound.in_memory_game_state import InMemoryGameState
from pinochle.domain.game import Game
from tests.ports.test_game_state_port import run_contract


def test_contract():
    run_contract(InMemoryGameState())


def test_overwrite_existing_game():
    store = InMemoryGameState()
    g = Game("g1")
    store.save(g)
    store.save(g)  # second save must not raise
    assert store.load("g1") is g


def test_load_missing_raises():
    store = InMemoryGameState()
    with pytest.raises(KeyError):
        store.load("missing")
