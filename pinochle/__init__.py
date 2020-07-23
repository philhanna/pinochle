__all__ = [
    'Suit', 'Rank', 'Card', 'Deck', 'set_seed'
]

from .suit import Suit
from .rank import Rank
from .card import Card
from .deck import Deck
from random import seed as SEED


def set_seed(x):
    """ Call this function with an integer x to start a fixed sequence """
    SEED(a=x)


set_seed(None)
