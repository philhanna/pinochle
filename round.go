package pinochle

import "github.com/philhanna/cards"

// ---------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------

// Round is one round of play
type Round struct {
	BidWinner *Player
	Trump     cards.Suit
}
