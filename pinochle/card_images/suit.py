from enum import Enum

from . import IS_WINDOWS


class Suit(Enum):
    SPADES = ('\u2660', "S", 0x1F0A0)
    HEARTS = ('\u2665', "H", 0x1F0B0)
    DIAMONDS = ('\u2666', "D", 0x1F0C0)
    CLUBS = ('\u2663', "C", 0x1F0D0)

    def __new__(cls, glyph: str, character: str, offset: int):
        obj = object.__new__(cls)  # Create a new instance
        obj._glyph = glyph
        obj._character = character
        obj._offset = offset
        return obj

    @property
    def glyph(self) -> str:
        return self._glyph

    @property
    def character(self) -> str:
        return self._character

    @property
    def offset(self) -> int:
        return self._offset

    def __str__(self):
        if IS_WINDOWS():
            return self.character
        else:
            return self.glyph      
