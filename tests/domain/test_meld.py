# tests.domain.test_meld
import pytest

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.meld import detect_meld, total_meld, MeldUnit

TRUMP = Suit.SPADES


def cards(*specs: tuple[Rank, Suit]) -> list[Card]:
    """Build ``Card`` objects from ``(rank, suit)`` tuples."""
    return [Card(r, s) for r, s in specs]


def meld_names(hand: list[Card], trump: Suit) -> set[str]:
    """Return only the meld names detected in ``hand``."""
    return {u.name for u in detect_meld(hand, trump)}


def test_run_detected():
    """A full trump sequence should score as a run."""
    hand = cards(
        (Rank.ACE, TRUMP), (Rank.TEN, TRUMP), (Rank.KING, TRUMP),
        (Rank.QUEEN, TRUMP), (Rank.JACK, TRUMP),
    )
    assert "Run" in meld_names(hand, TRUMP)
    assert total_meld(hand, TRUMP) >= 150


def test_double_run_detected():
    """Two full trump sequences should score as a double run."""
    hand = cards(
        (Rank.ACE, TRUMP), (Rank.TEN, TRUMP), (Rank.KING, TRUMP),
        (Rank.QUEEN, TRUMP), (Rank.JACK, TRUMP),
        (Rank.ACE, TRUMP), (Rank.TEN, TRUMP), (Rank.KING, TRUMP),
        (Rank.QUEEN, TRUMP), (Rank.JACK, TRUMP),
    )
    assert "Double Run" in meld_names(hand, TRUMP)
    assert total_meld(hand, TRUMP) >= 1500


def test_pinochle_detected():
    """The queen of spades and jack of diamonds should score pinochle."""
    hand = cards((Rank.QUEEN, Suit.SPADES), (Rank.JACK, Suit.DIAMONDS))
    assert "Pinochle" in meld_names(hand, Suit.HEARTS)


def test_double_pinochle_detected():
    """Two pinochle combinations should score double pinochle."""
    hand = cards(
        (Rank.QUEEN, Suit.SPADES), (Rank.JACK, Suit.DIAMONDS),
        (Rank.QUEEN, Suit.SPADES), (Rank.JACK, Suit.DIAMONDS),
    )
    assert "Double Pinochle" in meld_names(hand, Suit.HEARTS)


def test_100_aces_detected():
    """One ace in every suit should score 100 aces."""
    hand = cards(
        (Rank.ACE, Suit.SPADES), (Rank.ACE, Suit.HEARTS),
        (Rank.ACE, Suit.DIAMONDS), (Rank.ACE, Suit.CLUBS),
    )
    assert "100 Aces" in meld_names(hand, Suit.HEARTS)
    assert total_meld(hand, Suit.HEARTS) == 100


def test_marriage_non_trump():
    """A non-trump king and queen should score a standard marriage."""
    hand = cards((Rank.KING, Suit.HEARTS), (Rank.QUEEN, Suit.HEARTS))
    assert "Marriage" in meld_names(hand, TRUMP)
    assert total_meld(hand, TRUMP) == 20


def test_trump_nine():
    """A nine in trump should receive the trump-nine bonus."""
    hand = cards((Rank.NINE, TRUMP),)
    assert "Trump Nine" in meld_names(hand, TRUMP)
    assert total_meld(hand, TRUMP) == 10


def test_empty_hand_no_meld():
    """An empty hand should not produce any meld."""
    assert detect_meld([], TRUMP) == []
