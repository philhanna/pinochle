from pinochle import CardChoosingStrategy, BiddingStrategy


class Player:
    """ One of the four players in the game """
    def __init__(self, name):
        self.name = name
        self.bidding_strategy = BiddingStrategy()
        self.card_choosing_strategy = CardChoosingStrategy()
        self.hand = None

    @property
    def hand(self):
        return self._hand

    @hand.setter
    def hand(self, value):
        self._hand = value

    def make_bid(self, bidding):
        hand = self.hand
        return self.bidding_strategy.make_bid(hand, bidding)

    def choose_card(self, cards):
        """ Chooses a card from a list """
        return self.card_choosing_strategy.choose_card(cards)

    def __repr__(self):
        return f"{__class__.__name__}(\"{self.name}\")"

    def __str__(self):
        return self.name

    def hash(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name
