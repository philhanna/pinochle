package pinochle

import "fmt"

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

// -----------------------------------------------------------------------
// Methods
// -----------------------------------------------------------------------

// Returns a representation of the type as a string
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
