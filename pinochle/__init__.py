# Pinochle rules: https://en.wikipedia.org/wiki/Pinochle

from random import seed as SEED
from .suit import Suit
from .rank import Rank
from .card import Card, CardParser
from .player import Player
from .deck import Deck

__all__ = [
    'set_seed',
    "Suit",
    "Rank",
    "Card",
    "CardParser",
    "Player",
    'PASS',
    "Deck"
]

# Define a constant for a bid of PASS
PASS = -1


def set_seed(x: int | None):
    """ Call this function with an integer x to start a fixed sequence """
    SEED(a=x)


set_seed(None)

