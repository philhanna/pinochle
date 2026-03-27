# pinochle.domain.hand
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit


class Hand:
    """A player's current set of cards."""

    def __init__(self, cards: list[Card] | None = None):
        self._cards: list[Card] = list(cards) if cards else []

    def add(self, cards: list[Card]) -> None:
        self._cards.extend(cards)

    def remove(self, card: Card) -> None:
        self._cards.remove(card)

    def remove_many(self, cards: list[Card]) -> None:
        for card in cards:
            self.remove(card)

    def cards_of_suit(self, suit: Suit) -> list[Card]:
        return [c for c in self._cards if c.suit == suit]

    def has_suit(self, suit: Suit) -> bool:
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
        return len(self._cards)

    def __iter__(self):
        return iter(self._cards)

    def __contains__(self, card: Card) -> bool:
        return card in self._cards
