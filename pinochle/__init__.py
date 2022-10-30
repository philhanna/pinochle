from random import seed as SEED
from .suit import Suit
from .rank import Rank
from .card import Card, CardParser
from .deck import Deck
from .player import Player

# Define a constant for a bid of PASS
PASS = -1


def set_seed(x: int | None):
    """ Call this function with an integer x to start a fixed sequence """
    SEED(a=x)


set_seed(None)

__all__ = [
    'set_seed',
    "Suit",
    "Rank",
    "Card",
    "CardParser",
    "Deck",
    "Player",
    'PASS',
]
