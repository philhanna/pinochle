from cards import Rank, Suit

class Card:
    """ A Card is a combination of a Rank and a Suit """
    def __init__(self, rank: Rank, suit: Suit):
        self.rank = rank
        self.suit = suit