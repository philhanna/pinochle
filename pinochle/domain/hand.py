# pinochle.domain.hand
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit


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

    def legal_plays(self, lead_suit: Suit | None, trump: Suit) -> list[Card]:
        """Return the subset of cards that are legal to play.

        Rules (simplified):
        - If leading: any card.
        - If following: must follow suit if able.
        - If void in lead suit: must trump if able.
        - Otherwise: any card.
        """
        if lead_suit is None:
            return list(self._cards)
        if self.has_suit(lead_suit):
            return self.cards_of_suit(lead_suit)
        if self.has_suit(trump):
            return self.cards_of_suit(trump)
        return list(self._cards)

    def __len__(self) -> int:
        """Return the number of cards currently held."""
        return len(self._cards)

    def __iter__(self):
        """Iterate over cards in their current hand order."""
        return iter(self._cards)

    def __contains__(self, card: Card) -> bool:
        """Return whether ``card`` is present in the hand."""
        return card in self._cards
