from pinochle import Rank, Suit


class Card:
    """ A card in the pinochle deck """
    def __init__(self, rank: Rank, suit: Suit):
        self.rank = rank
        self.suit = suit

    def __str__(self):
        rankname = self.rank.fullname()
        suitname = self.suit.value.lower()
        output = f"{rankname} of {suitname}"
        return output
