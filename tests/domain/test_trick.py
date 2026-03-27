# tests.domain.test_trick
import pytest

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.trick import Trick


TRUMP = Suit.SPADES


def make_trick(plays: list[tuple[str, Rank, Suit]]) -> Trick:
    t = Trick(lead_player_id=plays[0][0], trump=TRUMP)
    for pid, rank, suit in plays:
        t.play(pid, Card(rank, suit))
    return t


def test_highest_lead_suit_wins():
    t = make_trick([
        ("N", Rank.ACE, Suit.HEARTS),
        ("E", Rank.TEN, Suit.HEARTS),
        ("S", Rank.KING, Suit.DIAMONDS),  # off-suit, irrelevant
        ("W", Rank.QUEEN, Suit.HEARTS),
    ])
    assert t.winner() == "N"


def test_trump_beats_lead_suit():
    t = make_trick([
        ("N", Rank.ACE, Suit.HEARTS),
        ("E", Rank.NINE, Suit.SPADES),   # trump
        ("S", Rank.KING, Suit.HEARTS),
        ("W", Rank.TEN, Suit.HEARTS),
    ])
    assert t.winner() == "E"


def test_higher_trump_wins():
    t = make_trick([
        ("N", Rank.ACE, Suit.HEARTS),
        ("E", Rank.NINE, Suit.SPADES),   # lower trump
        ("S", Rank.ACE, Suit.SPADES),    # higher trump
        ("W", Rank.QUEEN, Suit.HEARTS),
    ])
    assert t.winner() == "S"


def test_winner_raises_if_incomplete():
    t = Trick(lead_player_id="N", trump=TRUMP)
    t.play("N", Card(Rank.ACE, Suit.HEARTS))
    with pytest.raises(ValueError):
        t.winner()


def test_play_raises_after_four_cards():
    t = make_trick([
        ("N", Rank.ACE, Suit.HEARTS),
        ("E", Rank.TEN, Suit.HEARTS),
        ("S", Rank.KING, Suit.HEARTS),
        ("W", Rank.QUEEN, Suit.HEARTS),
    ])
    with pytest.raises(ValueError):
        t.play("N", Card(Rank.NINE, Suit.HEARTS))
