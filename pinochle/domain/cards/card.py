# pinochle.domain.cards.card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit


class Card:
    """An immutable playing card identified by its Rank and Suit.

    Cards are value objects: two ``Card`` instances with the same rank and
    suit compare equal and hash to the same value, making them safe to use
    as dictionary keys or set members.  Because a Pinochle deck contains two
    physical copies of every card, equality is purely structural (rank + suit);
    callers that need to distinguish the two copies must track them separately.
    """

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
