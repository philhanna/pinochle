# pinochle.domain.trick
from dataclasses import dataclass

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit


@dataclass
class TrickPlay:
    """Records one card played into a trick, pairing the card with its player.

    Internal to ``Trick``.  Distinct from the ``CardPlayed`` domain event in
    ``pinochle.domain.game``, which announces the same act to the table.

    Attributes:
        player_id: The player who played the card.
        card: The card that was played.
    """

    player_id: str
    card: Card


class Trick:
    """Tracks the four cards played in one trick and determines the winner.

    A trick begins when the leader plays a card, establishing the lead suit.
    Subsequent players add their cards via ``play()``.  Once all four cards
    are recorded (``is_complete`` is ``True``), ``winner()`` applies Pinochle
    trick-taking rules: trump beats non-trump; within the same suit the higher
    rank wins (by ``Rank.value``); a card of the lead suit loses to any trump.
    """

    def __init__(self, lead_player_id: str, trump: Suit):
        """Start a new trick with the leader and trump suit."""
        self.trump = trump
        self._plays: list[TrickPlay] = []
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
        self._plays.append(TrickPlay(player_id=player_id, card=card))

    @property
    def is_complete(self) -> bool:
        """Return whether all four cards for the trick have been played."""
        return len(self._plays) == 4

    @property
    def cards(self) -> list[Card]:
        """Return the cards in play order for the trick."""
        return [p.card for p in self._plays]

    @property
    def plays(self) -> list[TrickPlay]:
        """Return the (player_id, card) pairs in play order for the trick."""
        return list(self._plays)

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
