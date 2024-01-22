package pinochle

import "github.com/philhanna/cards"

// ---------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------

// Hand is one round of play
type Hand struct {
	BidWinner *Player
	Trump     cards.Suit
}
