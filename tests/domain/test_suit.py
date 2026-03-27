# tests.domain.test_suit
from unittest.mock import patch
import pytest

import pinochle.domain.cards.suit as suit_module
from pinochle.domain.cards import Suit


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
    """Each suit should expose its configured glyph, fallback, and offset."""
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
def test_suit_str(suit, expected_str_windows, expected_str_non_windows):
    """String conversion should switch between ASCII and glyph output by OS."""
    with patch.object(suit_module, "_is_windows", return_value=True):
        assert str(suit) == expected_str_windows

    with patch.object(suit_module, "_is_windows", return_value=False):
        assert str(suit) == expected_str_non_windows
