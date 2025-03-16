import pytest
from cards import Rank, Suit, Card

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
    """Test the __str__ method of Card."""
    card = Card(rank, suit)
    actual = str(card)
    expected = expected_str
    assert actual == expected
