# tests.strategies.test_computer_player_strategy
from pinochle.strategies.computer_player_strategy import ComputerPlayerStrategy
from pinochle.domain.bid import MINIMUM_BID
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.meld import total_meld


def make_hand(specs: list[tuple[Rank, Suit]]) -> list[Card]:
    """Build a hand from ``(rank, suit)`` tuples."""
    return [Card(r, s) for r, s in specs]


def test_choose_trump_picks_most_common_suit():
    """Trump selection should choose the suit that appears most often."""
    hand = make_hand([
        (Rank.ACE, Suit.SPADES),
        (Rank.KING, Suit.SPADES),
        (Rank.QUEEN, Suit.SPADES),
        (Rank.ACE, Suit.HEARTS),
        (Rank.TEN, Suit.DIAMONDS),
    ])
    assert ComputerPlayerStrategy.choose_trump(hand) == Suit.SPADES


def test_choose_play_picks_highest():
    """Play selection should choose the highest-ranked legal card."""
    legal = make_hand([
        (Rank.NINE, Suit.HEARTS),
        (Rank.KING, Suit.HEARTS),
        (Rank.ACE, Suit.HEARTS),
    ])
    assert ComputerPlayerStrategy.choose_play(legal) == Card(Rank.ACE, Suit.HEARTS)


# ---------------------------------------------------------------------------
# choose_bid (FR-75a)
# ---------------------------------------------------------------------------

def test_choose_bid_opens_at_the_minimum_when_the_hand_supports_it():
    """A hand with plenty of meld and aces should open at 250."""
    hand = make_hand([
        (Rank.KING, Suit.SPADES), (Rank.QUEEN, Suit.SPADES),
        (Rank.ACE, Suit.SPADES), (Rank.ACE, Suit.HEARTS),
        (Rank.ACE, Suit.DIAMONDS), (Rank.ACE, Suit.CLUBS),
        (Rank.NINE, Suit.SPADES), (Rank.TEN, Suit.SPADES),
        (Rank.JACK, Suit.SPADES), (Rank.NINE, Suit.HEARTS),
        (Rank.NINE, Suit.DIAMONDS), (Rank.NINE, Suit.CLUBS),
    ])
    assert ComputerPlayerStrategy.choose_bid(hand, current_high_bid=0) == 250


def test_choose_bid_opens_on_an_ordinary_good_hand():
    """FR-75a: a hand a person would open on must be able to open at 250.

    A royal marriage, a pinochle, a side marriage, the dix and an ace — good,
    but nothing exceptional: no run, no arounds. The regression this pins is
    that such a hand once passed, because a valuation confined to its own
    twelve cards cannot reach FR-27's minimum however strong it is.
    """
    hand = make_hand([
        (Rank.KING, Suit.SPADES), (Rank.QUEEN, Suit.SPADES),
        (Rank.ACE, Suit.SPADES), (Rank.TEN, Suit.SPADES),
        (Rank.NINE, Suit.SPADES), (Rank.JACK, Suit.DIAMONDS),
        (Rank.ACE, Suit.HEARTS), (Rank.KING, Suit.DIAMONDS),
        (Rank.QUEEN, Suit.DIAMONDS), (Rank.TEN, Suit.CLUBS),
        (Rank.JACK, Suit.CLUBS), (Rank.NINE, Suit.CLUBS),
    ])

    # The hand on its own is worth well under the minimum: the partner's
    # assumed contribution is what makes the contract reachable.
    own_worth = max(
        total_meld(hand, suit) + ComputerPlayerStrategy._trick_estimate(hand, suit)
        for suit in Suit
    )
    assert own_worth < MINIMUM_BID

    assert ComputerPlayerStrategy.choose_bid(hand, current_high_bid=0) == MINIMUM_BID


def test_choose_bid_stops_raising_an_ordinary_hand_eventually():
    """The partner allowance must not make a hand bid without limit.

    Deliberately far above any plausible valuation rather than one increment
    past this hand's: where the ceiling falls is a tuning decision, and a test
    that pins it would fail every time the allowance is adjusted.
    """
    hand = make_hand([
        (Rank.KING, Suit.SPADES), (Rank.QUEEN, Suit.SPADES),
        (Rank.ACE, Suit.SPADES), (Rank.TEN, Suit.SPADES),
        (Rank.NINE, Suit.SPADES), (Rank.JACK, Suit.DIAMONDS),
        (Rank.ACE, Suit.HEARTS), (Rank.KING, Suit.DIAMONDS),
        (Rank.QUEEN, Suit.DIAMONDS), (Rank.TEN, Suit.CLUBS),
        (Rank.JACK, Suit.CLUBS), (Rank.NINE, Suit.CLUBS),
    ])
    assert ComputerPlayerStrategy.choose_bid(hand, current_high_bid=1000) is None


def test_choose_bid_passes_on_a_weak_hand():
    """A hand with no meld and no strength should not open the bidding."""
    hand = make_hand([
        (Rank.NINE, Suit.SPADES), (Rank.NINE, Suit.HEARTS),
        (Rank.NINE, Suit.DIAMONDS), (Rank.NINE, Suit.CLUBS),
        (Rank.JACK, Suit.HEARTS), (Rank.JACK, Suit.CLUBS),
        (Rank.TEN, Suit.HEARTS), (Rank.TEN, Suit.CLUBS),
        (Rank.KING, Suit.HEARTS), (Rank.QUEEN, Suit.CLUBS),
        (Rank.TEN, Suit.DIAMONDS), (Rank.JACK, Suit.SPADES),
    ])
    assert ComputerPlayerStrategy.choose_bid(hand, current_high_bid=0) is None


def test_choose_bid_raises_by_one_increment_not_straight_to_the_estimate():
    """Bidding stops one raise past the current high, not at the ceiling."""
    hand = make_hand([
        (Rank.KING, Suit.SPADES), (Rank.QUEEN, Suit.SPADES),
        (Rank.ACE, Suit.SPADES), (Rank.ACE, Suit.HEARTS),
        (Rank.ACE, Suit.DIAMONDS), (Rank.ACE, Suit.CLUBS),
        (Rank.NINE, Suit.SPADES), (Rank.TEN, Suit.SPADES),
        (Rank.JACK, Suit.SPADES), (Rank.NINE, Suit.HEARTS),
        (Rank.NINE, Suit.DIAMONDS), (Rank.NINE, Suit.CLUBS),
    ])
    assert ComputerPlayerStrategy.choose_bid(hand, current_high_bid=250) == 260


def test_choose_bid_passes_once_the_current_high_exceeds_the_estimate():
    """A modest hand should stop raising once outbid past its worth."""
    hand = make_hand([
        (Rank.NINE, Suit.SPADES), (Rank.NINE, Suit.HEARTS),
        (Rank.NINE, Suit.DIAMONDS), (Rank.NINE, Suit.CLUBS),
        (Rank.JACK, Suit.HEARTS), (Rank.JACK, Suit.CLUBS),
        (Rank.TEN, Suit.HEARTS), (Rank.TEN, Suit.CLUBS),
        (Rank.KING, Suit.HEARTS), (Rank.QUEEN, Suit.CLUBS),
        (Rank.TEN, Suit.DIAMONDS), (Rank.JACK, Suit.SPADES),
    ])
    assert ComputerPlayerStrategy.choose_bid(hand, current_high_bid=250) is None


# ---------------------------------------------------------------------------
# choose_cards_to_pass (FR-75b)
# ---------------------------------------------------------------------------

def test_choose_cards_to_pass_prefers_trump_and_aces():
    """Passing should favor trump and aces over plain low cards."""
    hand = make_hand([
        (Rank.ACE, Suit.HEARTS), (Rank.KING, Suit.SPADES),
        (Rank.TEN, Suit.SPADES), (Rank.JACK, Suit.CLUBS),
        (Rank.NINE, Suit.DIAMONDS), (Rank.QUEEN, Suit.CLUBS),
    ])
    passed = ComputerPlayerStrategy.choose_cards_to_pass(hand, trump=Suit.SPADES, count=3)
    assert set(passed) == {
        Card(Rank.ACE, Suit.HEARTS),   # an ace, wherever it lies
        Card(Rank.TEN, Suit.SPADES),   # trump
        Card(Rank.KING, Suit.SPADES),  # trump
    }


def test_choose_cards_to_pass_keeps_a_marriage():
    """A king/queen pair of one suit should not be broken up to pass."""
    hand = make_hand([
        (Rank.KING, Suit.HEARTS), (Rank.QUEEN, Suit.HEARTS),  # marriage, not trump
        (Rank.ACE, Suit.SPADES), (Rank.NINE, Suit.SPADES),
        (Rank.TEN, Suit.SPADES), (Rank.JACK, Suit.CLUBS),
    ])
    passed = ComputerPlayerStrategy.choose_cards_to_pass(hand, trump=Suit.SPADES, count=4)
    assert Card(Rank.KING, Suit.HEARTS) not in passed
    assert Card(Rank.QUEEN, Suit.HEARTS) not in passed


def test_choose_cards_to_pass_keeps_pinochle():
    """Queen of spades + jack of diamonds should not be broken up to pass."""
    hand = make_hand([
        (Rank.QUEEN, Suit.SPADES), (Rank.JACK, Suit.DIAMONDS),
        (Rank.ACE, Suit.HEARTS), (Rank.NINE, Suit.CLUBS),
        (Rank.TEN, Suit.CLUBS), (Rank.JACK, Suit.CLUBS),
    ])
    passed = ComputerPlayerStrategy.choose_cards_to_pass(hand, trump=Suit.CLUBS, count=4)
    assert Card(Rank.QUEEN, Suit.SPADES) not in passed
    assert Card(Rank.JACK, Suit.DIAMONDS) not in passed


def test_choose_cards_to_pass_always_returns_exactly_count():
    """FR-42/FR-73: even an extremely meld-rich hand must pass exactly `count`."""
    hand = make_hand([
        # Two marriages, pinochle, and a trump nine: heavily protected.
        (Rank.KING, Suit.HEARTS), (Rank.QUEEN, Suit.HEARTS),
        (Rank.KING, Suit.CLUBS), (Rank.QUEEN, Suit.CLUBS),
        (Rank.QUEEN, Suit.SPADES), (Rank.JACK, Suit.DIAMONDS),
        (Rank.NINE, Suit.SPADES),
    ])
    passed = ComputerPlayerStrategy.choose_cards_to_pass(hand, trump=Suit.SPADES, count=4)
    assert len(passed) == 4


def test_choose_cards_to_pass_falls_back_to_low_filler_when_no_support_remains():
    """Without trump or aces available, the lowest remaining cards are passed."""
    hand = make_hand([
        (Rank.NINE, Suit.HEARTS), (Rank.JACK, Suit.HEARTS),
        (Rank.TEN, Suit.HEARTS), (Rank.KING, Suit.DIAMONDS),
        (Rank.QUEEN, Suit.CLUBS), (Rank.NINE, Suit.CLUBS),
    ])
    passed = ComputerPlayerStrategy.choose_cards_to_pass(hand, trump=Suit.SPADES, count=2)
    assert set(passed) == {Card(Rank.NINE, Suit.HEARTS), Card(Rank.NINE, Suit.CLUBS)}


# ---------------------------------------------------------------------------
# choose_draw_position (FR-11b, NFR-7)
# ---------------------------------------------------------------------------

def test_choose_draw_position_only_picks_an_untaken_position():
    """FR-11b: a computer draws at random from what is left of the spread."""
    strategy = ComputerPlayerStrategy()
    taken = {0, 1, 2, 4}
    for _ in range(20):
        assert strategy.choose_draw_position(taken, spread_size=6) in {3, 5}


def test_choose_draw_position_is_reproducible_from_a_seed():
    """NFR-7: a seed must reproduce a whole game, not only its shuffle.

    The draw picks the dealer, and the dealer decides which twelve cards of a
    shuffle each seat receives — so an unseeded draw would make a seeded deal
    unreproducible.
    """
    from random import Random

    first = ComputerPlayerStrategy(rng=Random(99))
    second = ComputerPlayerStrategy(rng=Random(99))
    draws = [(first.choose_draw_position(set(), 48), second.choose_draw_position(set(), 48))
             for _ in range(10)]
    assert all(a == b for a, b in draws)
    assert len({a for a, _ in draws}) > 1, "and it is actually random"


def test_choose_draw_position_raises_when_the_spread_is_exhausted():
    """Nothing left to draw is a programming error, not a silent no-op."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        ComputerPlayerStrategy().choose_draw_position({0, 1}, spread_size=2)
