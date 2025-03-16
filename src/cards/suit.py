from enum import Enum


class Suit(Enum):
    SPADES = (0x2660, "S", 0x1F0A0)
    HEARTS = (0x2661, "H", 0x1F0B0)
    DIAMONDS = (0x2662, "D", 0x1F0C0)
    CLUBS = (0x2663, "C", 0x1F0D0)

    def __new__(cls, glyph: int, character: str, offset: int):
        obj = object.__new__(cls)  # Create a new instance
        obj._glyph = glyph
        obj._character = character
        obj._offset = offset
        return obj
    
    @property
    def glyph(self):
        return self._glyph
    
    @property
    def character(self):
        return self._character
    
    @property
    def offset(self):
        return self._offset
