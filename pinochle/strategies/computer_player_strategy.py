# pinochle.strategies.computer_player_strategy
import random
from collections import Counter

from pinochle.domain.bid import BID_INCREMENT, MINIMUM_BID
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.meld import total_meld

# A conservative per-suit trick-taking estimate (FR-75a): each ace is worth
# roughly this many points of card-play strength, and each card of length in
# the suit beyond a normal four-card holding adds this much more.
_ACE_TRICK_VALUE = 15
_LENGTH_TRICK_VALUE = 10
_NORMAL_SUIT_LENGTH = 4

# What a bidder assumes its partner brings to the contract (FR-75a).
#
# A contract is a promise about the partnership's score, not about one hand:
# the bid team's total is both partners' meld plus the card points they take.
# Valuing only its own twelve cards, a bidder cannot reach FR-27's floor of
# 250 — measured over random deals, a hand's own meld plus its trick estimate
# has a median of 60 and clears 250 less than 1% of the time, so the strategy
# passed essentially always and rounds were abandoned under FR-31 instead of
# played.
#
# A single flat allowance, deliberately: it is a placeholder to be tuned by
# playing games, not a model of the partner's hand.
_PARTNER_CONTRIBUTION = 130


class ComputerPlayerStrategy:
    """Rule-based AI decision helpers.

    Provides stateless strategy methods for choosing a bid, trump, cards to
    pass, and which card to play.  Callers are responsible for loading hand
    state and submitting decisions through the appropriate port.

    Strategy:
    - Bidding: meld plus a conservative trick estimate, bid in 10s up to
      that estimate (FR-75a).
    - Trump: pick the suit with the most cards in hand.
    - Passing: give the partner cards that support the contract — trump and
      aces — while keeping whatever completes the passer's own meld
      (FR-75b).
    - Playing: always play the highest legal card.
    """

    @staticmethod
    def choose_draw_position(taken: set[int], spread_size: int) -> int:
        """Pick an untaken position from the face-down dealer-selection spread.

        The spread is face down, so no information distinguishes one position
        from another and a random untaken choice is exactly right.
        """
        available = [i for i in range(spread_size) if i not in taken]
        if not available:
            raise ValueError("No positions remain in the spread.")
        return random.choice(available)

    @staticmethod
    def choose_bid(hand_cards: list[Card], current_high_bid: int) -> int | None:
        """Bid the next increment while it stays within a conservative estimate.

        FR-75a: for each candidate trump suit, estimate the hand's worth as
        its meld in that suit plus a trick estimate from aces held and
        length in that suit; take the best suit's estimate, and add what the
        partner can be assumed to contribute (``_PARTNER_CONTRIBUTION``),
        since the contract is scored against the partnership.  Bidding one
        increment at a time (rather than jumping straight to the estimate)
        lets the auction stop as soon as someone else's estimate is higher,
        exactly as a cautious human bidder would.
        """
        estimate = _PARTNER_CONTRIBUTION + max(
            total_meld(hand_cards, suit) + ComputerPlayerStrategy._trick_estimate(hand_cards, suit)
            for suit in Suit
        )
        candidate = current_high_bid + BID_INCREMENT if current_high_bid else MINIMUM_BID
        return candidate if candidate <= estimate else None

    @staticmethod
    def _trick_estimate(hand_cards: list[Card], suit: Suit) -> int:
        """Return a conservative trick-taking estimate if ``suit`` were trump."""
        aces = sum(1 for c in hand_cards if c.rank == Rank.ACE and c.suit == suit)
        length = sum(1 for c in hand_cards if c.suit == suit)
        extra_length = max(0, length - _NORMAL_SUIT_LENGTH)
        return aces * _ACE_TRICK_VALUE + extra_length * _LENGTH_TRICK_VALUE

    @staticmethod
    def choose_trump(hand_cards: list[Card]) -> Suit:
        """Pick the suit with the most cards; break ties by suit order."""
        counts = {suit: sum(1 for c in hand_cards if c.suit == suit) for suit in Suit}
        return max(counts, key=lambda s: counts[s])

    @staticmethod
    def choose_cards_to_pass(hand_cards: list[Card], trump: Suit, count: int = 4) -> list[Card]:
        """Return ``count`` cards to pass: trump and aces, not the passer's own meld.

        FR-75b: cards that are part of a marriage, pinochle, an arounds set,
        or the trump nine are protected from being passed, even if they are
        trump or an ace.  If protecting meld would leave fewer than
        ``count`` cards to choose from — an unusually meld-rich hand — the
        least valuable protected cards are released instead, because FR-42
        requires exactly ``count`` cards and FR-73 forbids submitting an
        illegal one.
        """
        protected_budget = ComputerPlayerStrategy._protected_counts(hand_cards, trump)

        def take_protected(card: Card) -> bool:
            key = (card.rank, card.suit)
            if protected_budget.get(key, 0) > 0:
                protected_budget[key] -= 1
                return True
            return False

        def is_support(card: Card) -> bool:
            return card.suit == trump or card.rank == Rank.ACE

        indices = range(len(hand_cards))
        unprotected = [i for i in indices if not take_protected(hand_cards[i])]
        protected = [i for i in indices if i not in unprotected]

        support = sorted(
            (i for i in unprotected if is_support(hand_cards[i])),
            key=lambda i: -hand_cards[i].rank.value,
        )
        filler = sorted(
            (i for i in unprotected if not is_support(hand_cards[i])),
            key=lambda i: hand_cards[i].rank.value,
        )
        chosen = (support + filler)[:count]

        if len(chosen) < count:
            protected.sort(key=lambda i: hand_cards[i].rank.value)
            chosen = chosen + protected[:count - len(chosen)]

        return [hand_cards[i] for i in chosen]

    @staticmethod
    def _protected_counts(hand_cards: list[Card], trump: Suit) -> Counter:
        """Approximate which (rank, suit) cards complete the hand's own meld.

        A lightweight mirror of ``detect_meld``'s categories, used only to
        decide what not to pass — exact scoring is ``meld.py``'s job, and
        this only needs to be a reasonable guess at what to protect.
        """
        counts = Counter((c.rank, c.suit) for c in hand_cards)
        protected: Counter = Counter()

        for suit in Suit:
            if min(counts[(Rank.KING, suit)], counts[(Rank.QUEEN, suit)]):
                protected[(Rank.KING, suit)] += 1
                protected[(Rank.QUEEN, suit)] += 1

        if counts[(Rank.QUEEN, Suit.SPADES)] and counts[(Rank.JACK, Suit.DIAMONDS)]:
            protected[(Rank.QUEEN, Suit.SPADES)] += 1
            protected[(Rank.JACK, Suit.DIAMONDS)] += 1

        for rank in (Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK):
            if all(counts[(rank, s)] for s in Suit):
                for s in Suit:
                    protected[(rank, s)] += 1

        if counts[(Rank.NINE, trump)]:
            protected[(Rank.NINE, trump)] += 1

        return protected

    @staticmethod
    def choose_play(legal_cards: list[Card]) -> Card:
        """Return the highest-ranked card among the legal options."""
        return max(legal_cards, key=lambda c: c.rank.value)
