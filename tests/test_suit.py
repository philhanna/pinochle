import pytest

from pinochle import Suit


@pytest.mark.parametrize("name,suit", [
    ("Hearts", Suit.HEARTS),
    ("Clubs", Suit.CLUBS),
    ("Diamonds", Suit.DIAMONDS),
    ("Spades", Suit.SPADES),
])
def test_suit(name, suit):
    assert name == str(suit)
