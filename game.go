package pinochle

// ---------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------

// Game is a server that coordinates the actions of the players and the
// games.
type Game struct {
	Players [4]*Player
	NSTeam *Team
	EWTeam *Team
}

// HighestRank returns a pointer to the card with the highest rank.  If
// there is a tie, returns nil.
func HighestRank(cards []Card) *Card {
	switch len(cards) {
	case 0: // Empty hand
		return nil
	case 1: // Only one card
		return &cards[0]
	case 2: // Only two cards
	// TODO write me
	}
	return nil
}
