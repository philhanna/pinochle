from unittest.mock import patch
import pytest
from cards import IS_WINDOWS
from cards import Suit
import cards


@pytest.mark.parametrize(
    "suit, expected_glyph, expected_character, expected_offset",
    [
        (Suit.SPADES, "♠", "S", 0x1F0A0),
        (Suit.HEARTS, "♥", "H", 0x1F0B0),
        (Suit.DIAMONDS, "♦", "D", 0x1F0C0),
        (Suit.CLUBS, "♣", "C", 0x1F0D0),
    ],
)
def test_suit_properties(suit, expected_glyph, expected_character, expected_offset):
    """Test that Suit enum members have correct properties."""
    assert suit.glyph == expected_glyph
    assert suit.character == expected_character
    assert suit.offset == expected_offset


@pytest.mark.parametrize(
    "suit, expected_str_windows, expected_str_non_windows",
    [
        (Suit.SPADES, "S", "♠"),
        (Suit.HEARTS, "H", "♥"),
        (Suit.DIAMONDS, "D", "♦"),
        (Suit.CLUBS, "C", "♣"),
    ],
)
def test_suit_str(mocker, suit, expected_str_windows, expected_str_non_windows):
    """Test the __str__ method of Suit based on the platform."""

    # Mock IS_WINDOWS to return True and check string representation
    with patch.object(cards.suit, "IS_WINDOWS", return_value=True):
        assert str(suit) == expected_str_windows

    # Mock IS_WINDOWS to return False and check string representation
    with patch.object(cards.suit, "IS_WINDOWS", return_value=False):
        assert str(suit) == expected_str_non_windows