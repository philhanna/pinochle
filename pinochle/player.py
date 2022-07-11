from typing import Optional, List

from pinochle import DealerChoosingStrategy, BiddingStrategy, Hand, Card


class Player:
    """ One of the four players in the game """

    def __init__(self, name):
        self._name : str = name
        self._partner : Optional[Player] = None
        self._dealer_choosing_strategy : DealerChoosingStrategy = DealerChoosingStrategy()
        self._bidding_strategy: BiddingStrategy = BiddingStrategy()
        self._hand : Optional[Hand] = None

    @property
    def name(self) -> str:
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

    def choose_card(self, cards: List[Card]) -> Card :
        """ Chooses a card from a list. This is at the beginning of the game
        when a dealer is being chosen.
        """
        card: Card = self._dealer_choosing_strategy.choose_card(cards)
        return card

    def __repr__(self) -> str:
        return f"{__class__.__name__}(\"{self._name}\")"

    def __str__(self) -> str:
        return self._name

    def hash(self) -> int:
        return hash(self._name)

    def __eq__(self, other) -> bool:
        return self.name == other.name
