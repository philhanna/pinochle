__all__ = [
    'set_seed',
    'Suit', 'Rank', 'Card', 'Deck', 'Hand',
    'CardChoosingStrategy',
    'Player', 'Team'
]

from random import seed as SEED
from .suit import Suit
from .rank import Rank
from .card import Card
from .deck import Deck
from .hand import Hand
from .card_choosing_strategy import CardChoosingStrategy
from .player import Player
from .team import Team


def set_seed(x):
    """ Call this function with an integer x to start a fixed sequence """
    SEED(a=x)


set_seed(None)
