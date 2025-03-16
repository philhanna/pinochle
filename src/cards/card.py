from cards import Rank, Suit

class Card:
    """ A Card is a combination of a Rank and a Suit """
    def __init__(self, rank: Rank, suit: Suit):
        self.rank: Rank = rank
        self.suit: Suit = suit
        
    def __str__(self):
        result = str(self.rank) + str(self.suit)
        return result