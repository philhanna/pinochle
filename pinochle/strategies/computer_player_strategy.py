# pinochle.strategies.computer_player_strategy
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit


class ComputerPlayerStrategy:
    """Rule-based AI decision helpers.

    Provides stateless strategy methods for choosing trump, cards to pass,
    and which card to play.  Callers are responsible for loading hand state
    and submitting decisions through the appropriate port.

    Strategy:
    - Trump: pick the suit with the most cards in hand.
    - Passing: give the partner the four lowest-ranked cards.
    - Playing: always play the highest legal card.
    """

    @staticmethod
    def choose_trump(hand_cards: list[Card]) -> Suit:
        """Pick the suit with the most cards; break ties by suit order."""
        counts = {suit: sum(1 for c in hand_cards if c.suit == suit) for suit in Suit}
        return max(counts, key=lambda s: counts[s])

    @staticmethod
    def choose_cards_to_pass(hand_cards: list[Card], count: int = 4) -> list[Card]:
        """Return the `count` lowest-ranked cards to pass to partner."""
        return sorted(hand_cards, key=lambda c: c.rank.value)[:count]

    @staticmethod
    def choose_play(legal_cards: list[Card]) -> Card:
        """Return the highest-ranked card among the legal options."""
        return max(legal_cards, key=lambda c: c.rank.value)
