package pinochle

// ---------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------

// Round is one round of play
type Round struct {
	game      *Game
	dealer    *Player
	bidWinner *Player
	trump     Suit
}

// ---------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------

// NewRound starts a new round
func NewRound(g *Game, dealer *Player) *Round {

	// Create a new round
	r := new(Round)
	r.game = g
	r.dealer = dealer

	// Create a new deck
	deck := NewDeck()

	// Dealer shuffles at least once
	deck.Shuffle()
	for dealer.WantToReshuffle() {
		deck.Shuffle()
	}

	// Dealer offers player on right chance to cut
	other := g.PlayerOnRight(dealer)
	if other.WantToCut() {
		deck.Cut()
	}

	// Return a pointer to the round
	return r
}

// ---------------------------------------------------------------------
// Methods
// ---------------------------------------------------------------------
