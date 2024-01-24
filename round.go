package pinochle

// ---------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------

// Round is one round of play
type Round struct {
	BidWinner *Player
	Trump     Suit
}
