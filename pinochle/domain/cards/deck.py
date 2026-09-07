# pinochle.domain.cards.deck
import random

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit

# Pinochle uses two copies of each card (9 through Ace in each suit)
_PINOCHLE_RANKS = [Rank.NINE, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.TEN, Rank.ACE]
_PINOCHLE_SUITS = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]


class Deck:
    """A standard 48-card Pinochle deck containing two copies of every rank/suit combination.

    On construction the cards are in a deterministic suit-then-rank order.
    Call ``shuffle()`` before dealing to randomize them.  ``deal(n)`` removes
    cards from the top of the deck and returns them, so the deck shrinks with
    each call.  The deck does not regenerate cards; create a new ``Deck``
    instance to start a fresh deal.
    """

    def __init__(self):
        """Build a fresh ordered Pinochle deck."""
        self._cards: list[Card] = [
            Card(rank, suit)
            for suit in _PINOCHLE_SUITS
            for rank in _PINOCHLE_RANKS
            for _ in range(2)
        ]

    def shuffle(self, rng: random.Random | None = None) -> None:
        """Randomize the order of the remaining cards.

        Accepts an optional seeded ``Random`` (NFR-7), so a caller can make a
        deal reproducible; defaults to the module-level generator.
        """
        (rng or random).shuffle(self._cards)

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
        """Return the number of undealt cards still in the deck."""
        return len(self._cards)

    def __iter__(self):
        """Iterate over the remaining cards in deck order."""
        return iter(self._cards)
