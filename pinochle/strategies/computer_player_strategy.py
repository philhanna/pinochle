# pinochle.strategies.computer_player_strategy
import random
from collections import Counter

from pinochle.domain.bid import BID_INCREMENT, MINIMUM_BID, BidEntry
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

# The five ranks that make a run, in one suit: A-10-K-Q-J.
_RUN_RANKS = (Rank.ACE, Rank.TEN, Rank.KING, Rank.QUEEN, Rank.JACK)

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
_PARTNER_CONTRIBUTION = 180


class ComputerPlayerStrategy:
    """Rule-based AI decision helpers.

    Provides stateless strategy methods for choosing a bid, trump, cards to
    pass, and which card to play.  Callers are responsible for loading hand
    state and submitting decisions through the appropriate port.

    Strategy:
    - Bidding: meld plus a conservative trick estimate, bid in 10s up to
      that estimate (FR-75a), and give way rather than bid against a
      partner once both opponents have passed.
    - Trump: pick the suit with the most cards in hand.
    - Passing: give the partner every trump first, then aces, while keeping
      whatever completes the passer's own meld among the rest (FR-75b).
    - Playing: always play the highest legal card.
    """

    def __init__(self, rng: random.Random | None = None):
        """Hold the randomness source used for the dealer-selection draw.

        The only decision this strategy makes at random, so it is the only
        reason the class holds state at all and the only method below that is
        not static.  ``None`` means the module-level ``random``; a seeded
        ``Random`` makes a whole game reproducible (NFR-7), which a seeded
        shuffle alone does not — the draw picks the dealer, and the dealer
        decides which twelve cards of that shuffle each seat receives.
        """
        self._rng = rng or random

    def choose_draw_position(self, taken: set[int], spread_size: int) -> int:
        """Pick an untaken position from the face-down dealer-selection spread.

        The spread is face down, so no information distinguishes one position
        from another and a random untaken choice is exactly right.
        """
        available = [i for i in range(spread_size) if i not in taken]
        if not available:
            raise ValueError("No positions remain in the spread.")
        return self._rng.choice(available)

    @staticmethod
    def choose_bid(
        hand_cards: list[Card],
        current_high_bid: int,
        bid_history: list[BidEntry] | None = None,
        player_id: str | None = None,
        partner_id: str | None = None,
    ) -> int | None:
        """Bid the next increment while it stays within a conservative estimate.

        FR-75a: for each candidate trump suit, estimate the hand's worth as
        its meld in that suit plus a trick estimate from aces held and
        length in that suit; take the best suit's estimate, and add what the
        partner can be assumed to contribute (``_PARTNER_CONTRIBUTION``),
        since the contract is scored against the partnership.  Bidding one
        increment at a time (rather than jumping straight to the estimate)
        lets the auction stop as soon as someone else's estimate is higher,
        exactly as a cautious human bidder would.

        The valuation alone would go on bidding after both opponents have
        passed, when the only bidder left to beat is the partner; who the
        other seats are and what they have done is what says to stop, so
        ``bid_history``, ``player_id`` and ``partner_id`` are consulted for
        that.  Omitting them — as a test valuing a hand on its own does —
        leaves only the valuation.
        """
        estimate = _PARTNER_CONTRIBUTION + max(
            total_meld(hand_cards, suit) + ComputerPlayerStrategy._trick_estimate(hand_cards, suit)
            for suit in Suit
        )
        candidate = current_high_bid + BID_INCREMENT if current_high_bid else MINIMUM_BID
        if candidate > estimate:
            return None

        if bid_history is not None and player_id is not None and partner_id is not None:
            if ComputerPlayerStrategy._should_yield_to_partner(
                hand_cards, bid_history, player_id, partner_id
            ):
                return None

        return candidate

    @staticmethod
    def _trick_estimate(hand_cards: list[Card], suit: Suit) -> int:
        """Return a conservative trick-taking estimate if ``suit`` were trump."""
        aces = sum(1 for c in hand_cards if c.rank == Rank.ACE and c.suit == suit)
        length = sum(1 for c in hand_cards if c.suit == suit)
        extra_length = max(0, length - _NORMAL_SUIT_LENGTH)
        return aces * _ACE_TRICK_VALUE + extra_length * _LENGTH_TRICK_VALUE

    @staticmethod
    def _should_yield_to_partner(
        hand_cards: list[Card],
        bid_history: list[BidEntry],
        player_id: str,
        partner_id: str,
    ) -> bool:
        """Return ``True`` when this seat should stop bidding against its partner.

        Once both opponents have passed and both partners are still in, the
        auction is already won: every further bid raises the contract this
        partnership must make, against nobody.  The seat that has bid fewer
        times gives way, because the partnership has heard less about that
        hand than the other — and one of the two must, or they would raise
        each other until a valuation ran out.

        A seat holding a whole run (A-10-K-Q-J of one suit) is the
        exception: with the contract's best trump suit and 150 of meld in
        its own twelve cards, it is worth one bid to take the contract and
        name that suit itself.  One bid, though — if the partner answers
        with another bid instead of passing, this seat gives way on its
        next turn.
        """
        passed = {entry.player_id for entry in bid_history if entry.amount is None}
        if partner_id in passed or len(passed - {player_id, partner_id}) < 2:
            return False

        mine = ComputerPlayerStrategy._bid_count(bid_history, player_id)
        theirs = ComputerPlayerStrategy._bid_count(bid_history, partner_id)
        if mine >= theirs:
            return False

        if not ComputerPlayerStrategy._holds_a_run(hand_cards):
            return True

        duel = ComputerPlayerStrategy._entries_once_alone(bid_history, player_id, partner_id)
        return ComputerPlayerStrategy._bid_count(duel, player_id) > 0

    @staticmethod
    def _bid_count(bid_history: list[BidEntry], player_id: str) -> int:
        """Return how many actual bids, as opposed to passes, ``player_id`` made."""
        return sum(
            1 for entry in bid_history
            if entry.player_id == player_id and entry.amount is not None
        )

    @staticmethod
    def _holds_a_run(hand_cards: list[Card]) -> bool:
        """Return ``True`` if some suit's whole run is in this one hand."""
        counts = Counter((c.rank, c.suit) for c in hand_cards)
        return any(all(counts[(rank, suit)] for rank in _RUN_RANKS) for suit in Suit)

    @staticmethod
    def _entries_once_alone(
        bid_history: list[BidEntry],
        player_id: str,
        partner_id: str,
    ) -> list[BidEntry]:
        """Return the history from the moment the second opponent passed.

        What is counted in it is the one extra bid a run is worth: bids made
        earlier were made against opponents who were still bidding, and
        spending the exception on those would be spending it on nothing.
        """
        opponents_out: set[str] = set()
        for index, entry in enumerate(bid_history):
            if entry.amount is None and entry.player_id not in (player_id, partner_id):
                opponents_out.add(entry.player_id)
                if len(opponents_out) == 2:
                    return bid_history[index + 1:]
        return []

    @staticmethod
    def choose_trump(hand_cards: list[Card]) -> Suit:
        """Pick the suit with the most cards; break ties by suit order."""
        counts = {suit: sum(1 for c in hand_cards if c.suit == suit) for suit in Suit}
        return max(counts, key=lambda s: counts[s])

    @staticmethod
    def choose_cards_to_pass(hand_cards: list[Card], trump: Suit, count: int = 4) -> list[Card]:
        """Return ``count`` cards to pass: every trump first, then aces.

        FR-75b: trump takes priority over everything else — all of it goes,
        highest first, before an ace or anything else is considered, and
        before the passer's own meld is consulted.  Holding trump back to
        protect meld costs the partnership nothing to give up: the bid
        team's meld is both hands' meld added together, so a trump marriage
        or the trump nine scores the same in the bidder's hand as in the
        passer's, and in the bidder's hand it also plays.

        Among what is left, cards that are part of a marriage, pinochle, or
        an arounds set are protected from being passed, even if they are
        aces.  If protecting meld would leave fewer than ``count`` cards to
        choose from — an unusually meld-rich hand — the least valuable
        protected cards are released instead, because FR-42 requires exactly
        ``count`` cards and FR-73 forbids submitting an illegal one.
        """
        protected_budget = ComputerPlayerStrategy._protected_counts(hand_cards)

        def take_protected(card: Card) -> bool:
            key = (card.rank, card.suit)
            if protected_budget.get(key, 0) > 0:
                protected_budget[key] -= 1
                return True
            return False

        indices = range(len(hand_cards))
        trumps = sorted(
            (i for i in indices if hand_cards[i].suit == trump),
            key=lambda i: -hand_cards[i].rank.value,
        )
        others = [i for i in indices if hand_cards[i].suit != trump]
        unprotected = [i for i in others if not take_protected(hand_cards[i])]
        protected = [i for i in others if i not in unprotected]

        aces = [i for i in unprotected if hand_cards[i].rank == Rank.ACE]
        filler = sorted(
            (i for i in unprotected if hand_cards[i].rank != Rank.ACE),
            key=lambda i: hand_cards[i].rank.value,
        )
        chosen = (trumps + aces + filler)[:count]

        if len(chosen) < count:
            protected.sort(key=lambda i: hand_cards[i].rank.value)
            chosen = chosen + protected[:count - len(chosen)]

        return [hand_cards[i] for i in chosen]

    @staticmethod
    def _protected_counts(hand_cards: list[Card]) -> Counter:
        """Approximate which (rank, suit) cards complete the hand's own meld.

        A lightweight mirror of ``detect_meld``'s categories, used only to
        decide what not to pass — exact scoring is ``meld.py``'s job, and
        this only needs to be a reasonable guess at what to protect.  Trump
        is not consulted: ``choose_cards_to_pass`` passes every trump card
        ahead of this, so protecting the trump nine or a trump marriage
        could have no effect.
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

        return protected

    @staticmethod
    def choose_play(legal_cards: list[Card]) -> Card:
        """Return the highest-ranked card among the legal options."""
        return max(legal_cards, key=lambda c: c.rank.value)
