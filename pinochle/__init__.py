# Pinochle rules: https://en.wikipedia.org/wiki/Pinochle

__all__ = [
    'set_seed',
    "Suit",
    "Rank",
    "Card",
    "CardParser",
    "Player",
    'PASS',
]

# Define a constant for a bid of PASS
PASS = -1

from random import seed as SEED
from .suit import Suit
from .rank import Rank
from .card import Card, CardParser
from .player import Player


def set_seed(x):
    """ Call this function with an integer x to start a fixed sequence """
    SEED(a=x)


set_seed(None)

