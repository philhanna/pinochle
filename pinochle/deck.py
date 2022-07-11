from random import shuffle
from typing import List

from pinochle import Suit, Rank, Card


class Deck:
    """ The basic pinochle deck """
    def __init__(self):
        self.cards: List[Card] = [Card(rank, suit) for rank in Rank for suit in Suit]*2

    @property
    def cards(self) -> List[Card]:
        return self._cards

    @cards.setter
    def cards(self, value: List[Card]):
        self._cards = value

    def shuffle(self):
        """ Randomly permutes the cards in the deck """
        shuffle(self.cards)
