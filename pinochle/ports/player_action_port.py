# pinochle.ports.player_action_port
from abc import ABC, abstractmethod

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit


class PlayerActionPort(ABC):
    """Player-facing game actions exposed by the application layer."""

    @abstractmethod
    def draw_for_deal(self, game_id: str, player_id: str) -> Card:
        """Player draws a card to determine the dealer."""

    @abstractmethod
    def place_bid(self, game_id: str, player_id: str, amount: int | None) -> None:
        """Place a bid (amount=None means pass)."""

    @abstractmethod
    def name_trump(self, game_id: str, player_id: str, suit: Suit) -> None:
        """Bid winner names the trump suit."""

    @abstractmethod
    def pass_cards(self, game_id: str, player_id: str, cards: list[Card]) -> None:
        """Pass four cards to partner."""

    @abstractmethod
    def play_card(self, game_id: str, player_id: str, card: Card) -> None:
        """Play a card into the current trick."""
