# tests.adapters.test_computer_player
import pytest

from pinochle.adapters.computer_player_adapter import ComputerPlayerAdapter
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit


def make_hand(specs: list[tuple[Rank, Suit]]) -> list[Card]:
    return [Card(r, s) for r, s in specs]


def test_choose_trump_picks_most_common_suit():
    hand = make_hand([
        (Rank.ACE, Suit.SPADES),
        (Rank.KING, Suit.SPADES),
        (Rank.QUEEN, Suit.SPADES),
        (Rank.ACE, Suit.HEARTS),
        (Rank.TEN, Suit.DIAMONDS),
    ])
    assert ComputerPlayerAdapter.choose_trump(hand) == Suit.SPADES


def test_choose_cards_to_pass_returns_lowest():
    hand = make_hand([
        (Rank.ACE, Suit.SPADES),
        (Rank.NINE, Suit.HEARTS),
        (Rank.JACK, Suit.DIAMONDS),
        (Rank.QUEEN, Suit.CLUBS),
        (Rank.TEN, Suit.SPADES),
    ])
    passed = ComputerPlayerAdapter.choose_cards_to_pass(hand, count=4)
    assert Rank.ACE not in {c.rank for c in passed}
    assert len(passed) == 4


def test_choose_play_picks_highest():
    legal = make_hand([
        (Rank.NINE, Suit.HEARTS),
        (Rank.KING, Suit.HEARTS),
        (Rank.ACE, Suit.HEARTS),
    ])
    assert ComputerPlayerAdapter.choose_play(legal) == Card(Rank.ACE, Suit.HEARTS)
