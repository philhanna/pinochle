from random import shuffle

from pinochle import Suit, Rank, Card


class Deck:
    """ The basic pinochle deck """
    def __init__(self):
        self.cards = [Card(rank, suit) for rank in Rank for suit in Suit]*2

    @property
    def cards(self):
        return self._cards

    @cards.setter
    def cards(self, value):
        self._cards = value

    def shuffle(self):
        """ Randomly permutes the cards in the deck """
        shuffle(self.cards)
