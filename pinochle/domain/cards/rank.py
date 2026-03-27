# pinochle.domain.cards.rank
from enum import Enum


class Rank(Enum):
    NINE = (1, "9", "9")
    JACK = (2, "J", "jack")
    QUEEN = (3, "Q", "queen")
    KING = (4, "K", "king")
    TEN = (5, "10", "10")
    ACE = (6, "A", "ace")

    def __new__(cls, value, short_name, rank_name):
        obj = object.__new__(cls)
        obj._value_ = value
        obj._short_name = short_name
        obj._rank_name = rank_name
        return obj

    @property
    def short_name(self):
        return self._short_name

    @property
    def rank_name(self):
        return self._rank_name

    def __str__(self):
        return self.short_name
