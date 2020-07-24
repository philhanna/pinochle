from enum import Enum


class Rank(Enum):
    NINE = "9"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    TEN = "10"
    ACE = "A"

    def order(self):
        for i, rank in enumerate(Rank):
            if rank.name == self.name:
                return i

    def fullname(self):
        return ["nine", "jack", "queen", "king", "ten", "ace"][self.order()]

    def compare(self, other):
        return self.order() - other.order()

    def __gt__(self, other):
        return self.compare(other) > 0

    def __lt__(self, other):
        return self.compare(other) < 0

    def __eq__(self, other):
        return self.compare(other) == 0

    def __ge__(self, other):
        return self.compare(other) >= 0

    def __le__(self, other):
        return self.compare(other) <= 0

    def __ne__(self, other):
        return self.compare(other) != 0

    def __hash__(self):
        return hash(self.name)
