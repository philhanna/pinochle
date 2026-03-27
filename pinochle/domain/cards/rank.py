# pinochle.domain.cards.rank
from enum import Enum


class Rank(Enum):
    """Ranks used in Pinochle ordered from low to high."""

    NINE = (1, "9", "9")
    JACK = (2, "J", "jack")
    QUEEN = (3, "Q", "queen")
    KING = (4, "K", "king")
    TEN = (5, "10", "10")
    ACE = (6, "A", "ace")

    def __new__(cls, value, short_name, rank_name):
        """Construct an enum member with display metadata."""
        obj = object.__new__(cls)
        obj._value_ = value
        obj._short_name = short_name
        obj._rank_name = rank_name
        return obj

    @property
    def short_name(self):
        """Return the short label used in compact card notation."""
        return self._short_name

    @property
    def rank_name(self):
        """Return the lowercase filename-friendly rank name."""
        return self._rank_name

    def __str__(self):
        """Return the short display form for the rank."""
        return self.short_name
