package pinochle

import "runtime"

type Suit int

const (
	SPADES Suit = iota
	HEARTS
	DIAMONDS
	CLUBS
)

// Function to test whether the operating system is Windows.
// Declared as a variable so that it can be overridden in unit tests.
var (
	ISWINDOWS        = DEFAULTISWINDOWS
	DEFAULTISWINDOWS = func() bool {
		return runtime.GOOS == "windows"
	}
)

// A slice of the four suits
var Suits = []Suit{SPADES, HEARTS, DIAMONDS, CLUBS}

var Glyphs = map[Suit]string{
	SPADES:   string('\u2660'),
	HEARTS:   string('\u2661'),
	DIAMONDS: string('\u2662'),
	CLUBS:    string('\u2663'),
}

var Characters = map[Suit]string{
	SPADES:   "S",
	HEARTS:   "H",
	DIAMONDS: "D",
	CLUBS:    "C",
}

// Returns the Unicode glyph that represents this suit, i. e. ♠, ♡, ♢, ♣
func (suit Suit) Glyph() string {
	return Glyphs[suit]
}

// Returns the character that represents this suit, i. e. S, H, D, C
func (suit Suit) Character() string {
	return Characters[suit]
}

// Returns the suit as a string
func (suit Suit) String() string {
	if ISWINDOWS() {
		return suit.Character()
	} else {
		return suit.Glyph()
	}
}

// Returns the offset in the Unicode system to the beginning of cards
// for this suit
func (suit Suit) Offset() int {
	var offset int
	switch suit {
	case SPADES:
		offset = 0x1F0A0
	case HEARTS:
		offset = 0x1F0B0
	case DIAMONDS:
		offset = 0x1F0C0
	case CLUBS:
		offset = 0x1F0D0
	}
	return offset
}
