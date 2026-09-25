# pinochle.domain.hand
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit
from pinochle.domain.trick import Trick


class Hand:
    """A mutable collection of cards representing one player's current holding.

    Provides the card-management operations needed throughout a round: adding
    received cards, removing played or passed cards, and querying which cards
    are legal to play given the current trick context.  The hand does not
    enforce game rules itself — callers are responsible for invoking the
    correct methods in the right sequence.
    """

    def __init__(self, cards: list[Card] | None = None):
        """Initialize the hand with an optional starting card list."""
        self._cards: list[Card] = list(cards) if cards else []

    def add(self, cards: list[Card]) -> None:
        """Append multiple cards to the hand."""
        self._cards.extend(cards)

    def remove(self, card: Card) -> None:
        """Remove a single matching card from the hand."""
        self._cards.remove(card)

    def remove_many(self, cards: list[Card]) -> None:
        """Remove each card in ``cards`` from the hand."""
        for card in cards:
            self.remove(card)

    def cards_of_suit(self, suit: Suit) -> list[Card]:
        """Return all cards in the hand that match ``suit``."""
        return [c for c in self._cards if c.suit == suit]

    def has_suit(self, suit: Suit) -> bool:
        """Return whether the hand contains at least one card of ``suit``."""
        return any(c.suit == suit for c in self._cards)

    def legal_plays(self, trick: Trick | None, trump: Suit) -> list[Card]:
        """Return the subset of cards that may legally be played into ``trick``.

        A player must follow suit, but is obliged to beat the best card so far
        only when playing trump:

        - Leading, or no card played yet: any card.
        - Holding the led suit: must follow it.  If trump was led, must also
          beat the best trump already played if able.
        - Void in the led suit but holding trump: must trump, and must overtrump
          the best trump already played if able.
        - Void in both: any card.

        The whole trick is needed rather than just the led suit, because the
        obligation to overtrump depends on what has already been played.
        """
        if trick is None or not trick.cards:
            return list(self._cards)

        following = self.cards_of_suit(trick.lead_suit)
        if following:
            if trick.lead_suit == trump:
                return self._must_beat(following, trick.cards, trump)
            return following

        trumps = self.cards_of_suit(trump)
        if trumps:
            return self._must_beat(trumps, trick.cards, trump)

        return list(self._cards)

    @staticmethod
    def _must_beat(candidates: list[Card], played: list[Card], suit: Suit) -> list[Card]:
        """Narrow ``candidates`` to those beating the best ``suit`` card in ``played``.

        Falls back to the full set when nothing beats it, since the obligation
        is to win if you can, not to win at any cost.
        """
        in_suit = [c for c in played if c.suit == suit]
        if not in_suit:
            return candidates
        best = max(c.rank.value for c in in_suit)
        return [c for c in candidates if c.rank.value > best] or candidates

    def __len__(self) -> int:
        """Return the number of cards currently held."""
        return len(self._cards)

    def __iter__(self):
        """Iterate over cards in their current hand order."""
        return iter(self._cards)

    def __contains__(self, card: Card) -> bool:
        """Return whether ``card`` is present in the hand."""
        return card in self._cards
