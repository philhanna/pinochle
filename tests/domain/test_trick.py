# tests.domain.test_trick
import pytest

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.trick import Trick


TRUMP = Suit.SPADES


def make_trick(plays: list[tuple[str, Rank, Suit]]) -> Trick:
    """Build a trick from ``(player, rank, suit)`` tuples."""
    t = Trick(lead_player_id=plays[0][0], trump=TRUMP)
    for pid, rank, suit in plays:
        t.play(pid, Card(rank, suit))
    return t


def test_highest_lead_suit_wins():
    """Without trump, the highest card in the led suit should win."""
    t = make_trick([
        ("N", Rank.ACE, Suit.HEARTS),
        ("E", Rank.TEN, Suit.HEARTS),
        ("S", Rank.KING, Suit.DIAMONDS),  # off-suit, irrelevant
        ("W", Rank.QUEEN, Suit.HEARTS),
    ])
    assert t.winner() == "N"


def test_trump_beats_lead_suit():
    """Any trump card should beat cards in the led suit."""
    t = make_trick([
        ("N", Rank.ACE, Suit.HEARTS),
        ("E", Rank.NINE, Suit.SPADES),   # trump
        ("S", Rank.KING, Suit.HEARTS),
        ("W", Rank.TEN, Suit.HEARTS),
    ])
    assert t.winner() == "E"


def test_higher_trump_wins():
    """Among trump cards, the highest-ranked trump should win."""
    t = make_trick([
        ("N", Rank.ACE, Suit.HEARTS),
        ("E", Rank.NINE, Suit.SPADES),   # lower trump
        ("S", Rank.ACE, Suit.SPADES),    # higher trump
        ("W", Rank.QUEEN, Suit.HEARTS),
    ])
    assert t.winner() == "S"


def test_winner_raises_if_incomplete():
    """Winner calculation should fail until the trick has four cards."""
    t = Trick(lead_player_id="N", trump=TRUMP)
    t.play("N", Card(Rank.ACE, Suit.HEARTS))
    with pytest.raises(ValueError):
        t.winner()


def test_current_winner_is_none_before_the_lead():
    """Nobody is winning a trick no card has been played into."""
    assert Trick(lead_player_id="N", trump=TRUMP).current_winner is None


def test_current_winner_tracks_a_partial_trick():
    """The seat ahead so far is known before all four cards are down."""
    t = Trick(lead_player_id="N", trump=TRUMP)
    t.play("N", Card(Rank.KING, Suit.HEARTS))
    assert t.current_winner == "N"
    t.play("E", Card(Rank.ACE, Suit.HEARTS))
    assert t.current_winner == "E"
    t.play("S", Card(Rank.NINE, Suit.SPADES))  # trump
    assert t.current_winner == "S"


def test_current_winner_keeps_the_first_of_equal_cards():
    """A duplicate of the winning card does not take the lead from it."""
    t = Trick(lead_player_id="N", trump=TRUMP)
    t.play("N", Card(Rank.ACE, Suit.HEARTS))
    t.play("E", Card(Rank.ACE, Suit.HEARTS))
    assert t.current_winner == "N"


def test_play_raises_after_four_cards():
    """A fifth card should not be accepted into a completed trick."""
    t = make_trick([
        ("N", Rank.ACE, Suit.HEARTS),
        ("E", Rank.TEN, Suit.HEARTS),
        ("S", Rank.KING, Suit.HEARTS),
        ("W", Rank.QUEEN, Suit.HEARTS),
    ])
    with pytest.raises(ValueError):
        t.play("N", Card(Rank.NINE, Suit.HEARTS))
