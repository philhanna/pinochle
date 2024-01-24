package pinochle

import "fmt"

// -----------------------------------------------------------------------
// Type definitions
// -----------------------------------------------------------------------

// A rank is one of the 13 levels of cards in a deck.
type Rank int

const (
	TWO Rank = iota + 2
	THREE
	FOUR
	FIVE
	SIX
	SEVEN
	EIGHT
	NINE
	TEN
	JACK
	QUEEN
	KING
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
	case ACE:
		return "A"
	}
}

// Returns the offset in the Unicode system to the beginning of cards
// for this rank
func (r Rank) Offset() int {
	offset := 0
	switch r {
	case TWO:
		offset = 2
	case THREE:
		offset = 3
	case FOUR:
		offset = 4
	case FIVE:
		offset = 5
	case SIX:
		offset = 6
	case SEVEN:
		offset = 7
	case EIGHT:
		offset = 8
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
