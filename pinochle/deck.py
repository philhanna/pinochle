from typing import List

from pinochle import Card, Rank, Suit


class Deck:

    def  __init__(self):
        """ The basic pinochle deck """
        self._cards: List = [Card(rank, suit) for rank in Rank for suit in Suit] * 2
        print(self._cards)

   @property
    def cards(self):
        return self._cards
