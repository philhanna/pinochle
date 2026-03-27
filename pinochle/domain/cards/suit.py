# pinochle.domain.cards.suit
import platform
from enum import Enum


def _is_windows() -> bool:
    """Return whether the current platform is Windows."""
    return platform.system() == 'Windows'


class Suit(Enum):
    """Suits used in the deck along with display and asset metadata."""

    SPADES = ('\u2660', "S", 0x1F0A0)
    HEARTS = ('\u2665', "H", 0x1F0B0)
    DIAMONDS = ('\u2666', "D", 0x1F0C0)
    CLUBS = ('\u2663', "C", 0x1F0D0)

    def __new__(cls, glyph: str, character: str, offset: int):
        """Construct an enum member with glyph and card-sheet metadata."""
        obj = object.__new__(cls)
        obj._glyph = glyph
        obj._character = character
        obj._offset = offset
        return obj

    @property
    def glyph(self) -> str:
        """Return the Unicode suit glyph."""
        return self._glyph

    @property
    def character(self) -> str:
        """Return the ASCII fallback character for the suit."""
        return self._character

    @property
    def offset(self) -> int:
        """Return the suit offset used by the playing-card codepoints."""
        return self._offset

    def __str__(self):
        """Return an OS-appropriate display form for the suit."""
        if _is_windows():
            return self.character
        else:
            return self.glyph
