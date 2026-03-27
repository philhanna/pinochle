# pinochle.domain.cards.deck
import random

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit

# Pinochle uses two copies of each card (9 through Ace in each suit)
_PINOCHLE_RANKS = [Rank.NINE, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.TEN, Rank.ACE]
_PINOCHLE_SUITS = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]


class Deck:
    """A 48-card Pinochle deck: two copies of each rank/suit combination."""

    def __init__(self):
        self._cards: list[Card] = [
            Card(rank, suit)
            for suit in _PINOCHLE_SUITS
            for rank in _PINOCHLE_RANKS
            for _ in range(2)
        ]

    def shuffle(self) -> None:
        random.shuffle(self._cards)

    def deal(self, count: int) -> list[Card]:
        """Remove and return `count` cards from the top of the deck."""
        if count > len(self._cards):
            raise ValueError(
                f"Cannot deal {count} cards; only {len(self._cards)} remain."
            )
        dealt = self._cards[:count]
        self._cards = self._cards[count:]
        return dealt

    def __len__(self) -> int:
        return len(self._cards)

    def __iter__(self):
        return iter(self._cards)
