# Pinochle rules: https://en.wikipedia.org/wiki/Pinochle

__all__ = [
    'set_seed',
    'Suit', 'Rank', 'Card', 'Deck', 'Hand',
    'CardParser',
    'DealerChoosingStrategy',
    'BiddingStrategy',
    'Player',
    'PASS',
    'Bidding',
    'Round',
    'Game'
]

# Define a constant for a bid of PASS
PASS = -1

from random import seed as SEED
from .suit import Suit
from .rank import Rank
from .card import Card, CardParser
from .deck import Deck
from .hand import Hand
from .dealer_choosing_strategy import DealerChoosingStrategy
from .bidding_strategy import BiddingStrategy
from .player import Player
from .bidding import Bidding
from .round import Round
from .game import Game


def set_seed(x):
    """ Call this function with an integer x to start a fixed sequence """
    SEED(a=x)


set_seed(None)

