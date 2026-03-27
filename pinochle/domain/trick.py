# pinochle.domain.trick
from dataclasses import dataclass

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit


@dataclass
class CardPlayed:
    """A single play entry within a trick."""

    player_id: str
    card: Card


class Trick:
    """Tracks the four cards played in one trick and determines the winner."""

    def __init__(self, lead_player_id: str, trump: Suit):
        """Start a new trick with the leader and trump suit."""
        self.trump = trump
        self._plays: list[CardPlayed] = []
        self._lead_player_id = lead_player_id

    @property
    def lead_suit(self) -> Suit | None:
        """Return the led suit once the first card has been played."""
        if not self._plays:
            return None
        return self._plays[0].card.suit

    def play(self, player_id: str, card: Card) -> None:
        """Append one played card to the trick in play order."""
        if len(self._plays) >= 4:
            raise ValueError("Trick already has four cards.")
        self._plays.append(CardPlayed(player_id=player_id, card=card))

    @property
    def is_complete(self) -> bool:
        """Return whether all four cards for the trick have been played."""
        return len(self._plays) == 4

    @property
    def cards(self) -> list[Card]:
        """Return the cards in play order for the trick."""
        return [p.card for p in self._plays]

    def winner(self) -> str:
        """Return the player_id of the trick winner.

        Highest trump wins; if no trump played, highest card of lead suit wins.
        Within a suit, the higher rank (by Rank.value) wins.
        """
        if not self.is_complete:
            raise ValueError("Trick is not yet complete.")

        lead = self.lead_suit
        winning_play = self._plays[0]

        for played in self._plays[1:]:
            card = played.card
            current_winner_card = winning_play.card

            current_is_trump = current_winner_card.suit == self.trump
            new_is_trump = card.suit == self.trump

            if new_is_trump and not current_is_trump:
                winning_play = played
            elif new_is_trump and current_is_trump:
                if card.rank.value > current_winner_card.rank.value:
                    winning_play = played
            elif not new_is_trump and card.suit == lead:
                if (current_winner_card.suit != self.trump
                        and card.rank.value > current_winner_card.rank.value):
                    winning_play = played

        return winning_play.player_id
