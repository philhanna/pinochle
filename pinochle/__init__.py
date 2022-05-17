# Pinochle rules: https://en.wikipedia.org/wiki/Pinochle

__all__ = [
    'set_seed',
    'Suit', 'Rank', 'Card', 'Deck', 'Hand',
    'CardChoosingStrategy',
    'Player',
    'Bidding',
    'Round',
    'PASS',
    'Game'
]

from random import seed as SEED
from .suit import Suit
from .rank import Rank
from .card import Card
from .deck import Deck
from .hand import Hand
from .bidding import Bidding
from .card_choosing_strategy import CardChoosingStrategy
from .player import Player
from .round import Round
from .game import Game


def set_seed(x):
    """ Call this function with an integer x to start a fixed sequence """
    SEED(a=x)


set_seed(None)

# Define a constant for a bid of PASS
PASS = -1
