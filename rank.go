package pinochle

import (
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

var offsetMap = map[Rank]int{
	NINE:  9,
	JACK:  11,
	QUEEN: 13,
	KING:  14,
	TEN:   10,
	ACE:   1,
}

var shortNameMap = map[Rank]string{
	NINE:  "9",
	JACK:  "J",
	QUEEN: "Q",
	KING:  "K",
	TEN:   "10",
	ACE:   "A",
}

var rankNameMap = map[Rank]string{
	NINE:  "9",
	JACK:  "jack",
	QUEEN: "queen",
	KING:  "king",
	TEN:   "10",
	ACE:   "ace",
}

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
	return offsetMap[r]
}

// Returns a representation of a Rank as a string
func (r Rank) String() string {
	return shortNameMap[r]
}
