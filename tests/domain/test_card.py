# tests.domain.test_card
import pytest

from pinochle.domain.cards import Card, Rank, Suit


@pytest.mark.parametrize(
    "rank, suit, expected_str",
    [
        (Rank.ACE, Suit.SPADES, "A♠"),
        (Rank.TEN, Suit.HEARTS, "10♥"),
        (Rank.KING, Suit.DIAMONDS, "K♦"),
        (Rank.JACK, Suit.SPADES, "J♠"),
        (Rank.QUEEN, Suit.CLUBS, "Q♣"),
    ],
)
def test_card_str(rank, suit, expected_str):
    card = Card(rank, suit)
    assert str(card) == expected_str


def test_card_equality():
    assert Card(Rank.ACE, Suit.SPADES) == Card(Rank.ACE, Suit.SPADES)


def test_card_inequality():
    assert Card(Rank.ACE, Suit.SPADES) != Card(Rank.ACE, Suit.HEARTS)


def test_card_hashable():
    cards = {Card(Rank.ACE, Suit.SPADES), Card(Rank.ACE, Suit.SPADES)}
    assert len(cards) == 1
