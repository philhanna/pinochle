package pinochle

import (
	"fmt"
	"slices"
)

// -----------------------------------------------------------------------
// Type definitions
// -----------------------------------------------------------------------

// A rank is one of the six levels of cards in a pinochle deck.
type Rank int

const (
	NINE Rank = iota + 9
	JACK
	QUEEN
	KING
	TEN
	ACE
)

// Ranks is a slice of the six ranks in ascending order of precedence
var Ranks = []Rank{NINE, JACK, QUEEN, KING, TEN, ACE}

// -----------------------------------------------------------------------
// Methods
// -----------------------------------------------------------------------

// Less returns true if this rank is less than that of the other
func (r Rank) Less(other Rank) bool {
	return slices.Index(Ranks, r) < slices.Index(Ranks, other)
}

// Returns the offset in the Unicode system to the beginning of cards
// for this rank
func (r Rank) Offset() int {
	offset := 0
	switch r {
	case NINE:
		offset = 9
	case TEN:
		offset = 10
	case JACK:
		offset = 11
	case QUEEN:
		offset = 13
	case KING:
		offset = 14
	case ACE:
		offset = 1
	}
	return offset
}

// Returns a representation of a Rank as a string
func (r Rank) String() string {
	switch r {
	default:
		return fmt.Sprint(int(r))
	case JACK:
		return "J"
	case QUEEN:
		return "Q"
	case KING:
		return "K"
	case TEN:
		return "10"
	case ACE:
		return "A"
	}
}
