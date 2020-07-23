from pinochle import Suit, Rank, Card


class Deck:
    """ The basic pinochle deck """
    def __init__(self):
        self._cards = [Card(rank, suit) for rank in Rank for suit in Suit]*2

    @property
    def cards(self):
        return self._cards
