# pinochle.domain.cards.card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit


class Card:
    """A Card is a combination of a Rank and a Suit."""

    def __init__(self, rank: Rank, suit: Suit):
        """Create a card with the supplied rank and suit."""
        self.rank: Rank = rank
        self.suit: Suit = suit

    def __str__(self):
        """Return the compact human-readable card label."""
        return str(self.rank) + str(self.suit)

    def __eq__(self, other):
        """Compare cards by rank and suit."""
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        """Make cards usable as dictionary keys and set members."""
        return hash((self.rank, self.suit))

    def __repr__(self):
        """Return a debugging representation of the card."""
        return f"Card({self.rank!r}, {self.suit!r})"
