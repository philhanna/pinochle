from typing import Optional, List

from pinochle import Card


class Player:
    """ One of the four players in the game """

    def __init__(self, name: str):
        self._name : str = name
        self._partner : Optional["Player"] = None
        self._cards : List[Card] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def partner(self):
        return self._partner

    @partner.setter
    def partner(self, value: "Player"):
        self._partner = value

    def add_card_to_hand(self, card: Card) -> None:
        self._cards.append(card)

    def __repr__(self) -> str:
        return f"{__class__.__name__}(\"{self._name}\")"

    def __str__(self) -> str:
        return self._name

    def hash(self) -> int:
        return hash(self._name)

    def __eq__(self, other) -> bool:
        return self.name == other.name
