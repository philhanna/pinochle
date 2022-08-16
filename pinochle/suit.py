from enum import Enum


class Suit(Enum):
    """ An enumeration of the four suits in a pinochle deck """
    HEARTS = "Hearts"
    CLUBS = "Clubs"
    DIAMONDS = "Diamonds"
    SPADES = "Spades"

    def order(self) -> int:
        for i, suit in enumerate(Suit):
            if suit.name == self.name:
                return i

    def compare(self, other) -> int:
        return self.order() - other.order()

    def __str__(self) -> str :
        return str(self.value)

    def __gt__(self, other) -> bool:
        return self.compare(other) > 0

    def __eq__(self, other) -> bool:
        return self.compare(other) == 0

    def __hash__(self) -> int:
        return hash(self.name)
