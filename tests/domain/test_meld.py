# tests.domain.test_meld
import pytest

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.meld import MeldUnit, cards_in_meld, detect_meld, total_meld

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


RUN = ((Rank.ACE, TRUMP), (Rank.TEN, TRUMP), (Rank.KING, TRUMP),
       (Rank.QUEEN, TRUMP), (Rank.JACK, TRUMP))


def test_run_alone_scores_no_royal_marriage():
    """The King and Queen inside a run are consumed by it."""
    hand = cards(*RUN)
    assert "Royal Marriage" not in meld_names(hand, TRUMP)
    assert total_meld(hand, TRUMP) == 150


def test_run_plus_spare_pair_scores_a_royal_marriage():
    """A second trump King and Queen beyond the run melds as 40 (FR-49)."""
    hand = cards(*RUN, (Rank.KING, TRUMP), (Rank.QUEEN, TRUMP))
    assert "Royal Marriage" in meld_names(hand, TRUMP)
    assert total_meld(hand, TRUMP) == 190


def test_double_run_consumes_both_pairs():
    """Two runs use both trump King-Queen pairs, leaving no marriage."""
    hand = cards(*RUN, *RUN)
    assert "Royal Marriage" not in meld_names(hand, TRUMP)
    assert total_meld(hand, TRUMP) == 1500


def test_royal_marriages_without_a_run():
    """With no run, each trump King-Queen pair melds in full."""
    hand = cards((Rank.KING, TRUMP), (Rank.QUEEN, TRUMP))
    assert total_meld(hand, TRUMP) == 40
    doubled = cards((Rank.KING, TRUMP), (Rank.QUEEN, TRUMP),
                    (Rank.KING, TRUMP), (Rank.QUEEN, TRUMP))
    assert total_meld(doubled, TRUMP) == 80


def test_trump_nine():
    """A nine in trump should receive the trump-nine bonus."""
    hand = cards((Rank.NINE, TRUMP),)
    assert "Trump Nine" in meld_names(hand, TRUMP)
    assert total_meld(hand, TRUMP) == 10


def test_empty_hand_no_meld():
    """An empty hand should not produce any meld."""
    assert detect_meld([], TRUMP) == []


def test_only_cards_participating_in_meld_are_exposed():
    """Dead cards stay private when the player's meld is laid down."""
    hand = cards(
        (Rank.KING, Suit.HEARTS), (Rank.QUEEN, Suit.HEARTS),
        (Rank.ACE, Suit.CLUBS),
    )
    assert cards_in_meld(hand, TRUMP) == hand[:2]


def test_one_physical_card_shared_by_two_combinations_is_exposed_once():
    """The spade queen can serve queens-around and pinochle simultaneously."""
    hand = cards(
        (Rank.QUEEN, Suit.SPADES), (Rank.QUEEN, Suit.HEARTS),
        (Rank.QUEEN, Suit.DIAMONDS), (Rank.QUEEN, Suit.CLUBS),
        (Rank.JACK, Suit.DIAMONDS), (Rank.ACE, Suit.CLUBS),
    )
    exposed = cards_in_meld(hand, Suit.HEARTS)
    assert exposed == hand[:5]
    assert exposed.count(Card(Rank.QUEEN, Suit.SPADES)) == 1


def test_double_combinations_expose_both_physical_copies():
    """A double pinochle lays down both queens and both jacks."""
    hand = cards(
        (Rank.QUEEN, Suit.SPADES), (Rank.JACK, Suit.DIAMONDS),
        (Rank.QUEEN, Suit.SPADES), (Rank.JACK, Suit.DIAMONDS),
    )
    assert cards_in_meld(hand, Suit.HEARTS) == hand
