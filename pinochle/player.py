from pinochle import CardChoosingStrategy, Hand


class Player:
    """ One of the four players in the game """

    def __init__(self, name):
        self._name : str = name
        self._partner : Player = None
        self._card_choosing_strategy : CardChoosingStrategy = CardChoosingStrategy()
        self._hand : Hand = None

    @property
    def name(self):
        return self._name

    @property
    def partner(self):
        return self._partner

    @partner.setter
    def partner(self, value):
        self._partner = value

    @property
    def hand(self):
        return self._hand

    @hand.setter
    def hand(self, value):
        self._hand = value

    def choose_card(self, cards):
        """ Chooses a card from a list """
        return self._card_choosing_strategy.choose_card(cards)

    def __repr__(self):
        return f"{__class__.__name__}(\"{self._name}\")"

    def __str__(self):
        return self._name

    def hash(self):
        return hash(self._name)

    def __eq__(self, other):
        return self.name == other.name
