# tests.domain.test_scoring
import pytest

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.trick import Trick
from pinochle.domain.scoring import (
    LAST_TRICK_BONUS,
    resolve_round,
    resolve_toss_in,
    score_cards,
    score_tricks,
)

TRUMP = Suit.SPADES
PLAYER_TEAM = {"N": "NS", "E": "EW", "S": "NS", "W": "EW"}


def make_complete_trick(plays: list[tuple[str, Rank, Suit]]) -> Trick:
    """Build a fully played trick from ``(player, rank, suit)`` tuples."""
    t = Trick(lead_player_id=plays[0][0], trump=TRUMP)
    for pid, rank, suit in plays:
        t.play(pid, Card(rank, suit))
    return t


def test_score_cards_aces_and_tens():
    """Aces and tens should each contribute ten trick points."""
    cards = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.TEN, Suit.CLUBS)]
    assert score_cards(cards) == 20


def test_score_cards_kings_and_queens():
    """Kings and queens should each contribute five trick points."""
    cards = [Card(Rank.KING, Suit.HEARTS), Card(Rank.QUEEN, Suit.CLUBS)]
    assert score_cards(cards) == 10


def test_score_cards_jacks_and_nines_worth_zero():
    """Jacks and nines should not contribute trick points."""
    cards = [Card(Rank.JACK, Suit.HEARTS), Card(Rank.NINE, Suit.CLUBS)]
    assert score_cards(cards) == 0


def test_score_tricks_includes_last_trick_bonus():
    """The team that wins the last trick should receive the bonus."""
    trick = make_complete_trick([
        ("N", Rank.ACE, Suit.HEARTS),
        ("E", Rank.TEN, Suit.HEARTS),
        ("S", Rank.NINE, Suit.HEARTS),
        ("W", Rank.JACK, Suit.HEARTS),
    ])
    # N wins (highest of lead suit), last trick winner = N
    scores = score_tricks([trick], last_trick_winner_id="N", player_team=PLAYER_TEAM)
    # Cards: A(10) + 10(10) + 9(0) + J(0) = 20, plus last trick bonus 10 → NS=30
    assert scores["NS"] == 20 + LAST_TRICK_BONUS


def test_resolve_round_bid_met():
    """The bidding team should keep meld and trick points when it makes contract."""
    trick_scores = {"NS": 60, "EW": 30}
    meld_scores = {"NS": 200, "EW": 80}
    net = resolve_round(trick_scores, meld_scores, bid_team_id="NS", contract=250)
    assert net["NS"] == 260   # 60 tricks + 200 meld
    assert net["EW"] == 110   # 30 tricks + 80 meld


def test_resolve_round_going_set():
    """The bidding team should lose contract plus meld when it goes set."""
    trick_scores = {"NS": 20, "EW": 70}
    meld_scores = {"NS": 200, "EW": 80}
    # NS bid 300, total = 20 + 200 = 220 < 300 → going set
    net = resolve_round(trick_scores, meld_scores, bid_team_id="NS", contract=300)
    assert net["NS"] == -(300 + 200)


def test_resolve_round_non_bidder_no_tricks():
    """The non-bidding team should forfeit meld if it wins no tricks."""
    trick_scores = {"NS": 120, "EW": 0}
    meld_scores = {"NS": 150, "EW": 60}
    net = resolve_round(trick_scores, meld_scores, bid_team_id="NS", contract=250)
    assert net["EW"] == 0  # no tricks → forfeits meld


# ---------------------------------------------------------------------------
# Tossing the contract in
# ---------------------------------------------------------------------------

def test_toss_in_costs_the_bidding_team_the_contract():
    """Conceding deducts the bid and nothing else."""
    net = resolve_toss_in({"NS": 90, "EW": 40}, bid_team_id="NS", contract=300)
    assert net["NS"] == -300


def test_toss_in_leaves_the_opponents_their_meld():
    """The other team keeps its meld; no trick points exist either way."""
    net = resolve_toss_in({"NS": 90, "EW": 40}, bid_team_id="NS", contract=300)
    assert net["EW"] == 40


def test_tossing_in_costs_less_than_going_set():
    """Conceding caps the loss at the bid; playing on and failing also forfeits meld.

    This asymmetry is the whole point of the option: once a hand is plainly
    unmakeable, giving it up is cheaper than proving it.
    """
    meld = {"NS": 90, "EW": 40}
    conceded = resolve_toss_in(meld, bid_team_id="NS", contract=300)
    played_and_failed = resolve_round(
        {"NS": 60, "EW": 190}, meld, bid_team_id="NS", contract=300)
    assert conceded["NS"] == -300
    assert played_and_failed["NS"] == -390
    assert conceded["NS"] > played_and_failed["NS"]
