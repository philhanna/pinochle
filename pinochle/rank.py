from enum import Enum
from functools import total_ordering


@total_ordering
class Rank(Enum):
    NINE = "9"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    TEN = "10"
    ACE = "A"

    def order(self) -> int:
        for i, rank in enumerate(Rank):
            if rank.name == self.name:
                return i

    def fullname(self) -> str:
        return ["Nine", "Jack", "Queen", "King", "10", "Ace"][self.order()]

    def compare(self, other):
        return self.order() - other.order()

    def __gt__(self, other):
        return self.compare(other) > 0

    def __eq__(self, other):
        return self.compare(other) == 0

    def __hash__(self):
        return hash(self.name)
