from pinochle import CardChoosingStrategy


class Player:
    """ One of the four players in the game """
    def __init__(self, name):
        self.name = name
        self.card_choosing_strategy = CardChoosingStrategy()
        self.hand = None

    @property
    def hand(self):
        return self._hand

    @hand.setter
    def hand(self, value):
        self._hand = value

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
