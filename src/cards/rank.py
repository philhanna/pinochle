from enum import Enum


class Rank(Enum):
    NINE = (1, "9", "9")
    JACK = (2, "J", "jack")
    QUEEN = (3, "Q", "queen")
    KING = (4, "K", "king")
    TEN = (5, "10", "10")
    ACE = (6, "A", "ace")

    def __init__(self, value, short_name, rank_name):
        self._value_ = value
        self._short_name = short_name
        self._rank_name = rank_name

    @property
    def short_name(self):
        return self._short_name

    @property
    def rank_name(self):
        return self._rank_name
