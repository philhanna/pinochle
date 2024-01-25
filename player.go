package pinochle

import "math/rand"

// ---------------------------------------------------------------------
// Type definitions
// ---------------------------------------------------------------------

// Player is one of the four participants in the game.
type Player struct {
	ID       string
	Name     string
	Position uint8
	TeamID   string
	Hand     Hand
}

// HumanPlayer is a Player that supplies responses over the network
type HumanPlayer struct {
	Player
	Host string
	Port int
}

// ComputerPlayer is a Player that supplies default responses
type ComputerPlayer struct {
	Player
}

// ---------------------------------------------------------------------
// Methods
// ---------------------------------------------------------------------

// DrawCard returns a card drawn at random
func (p *Player) DrawCard(deck Deck) Card {
	n := deck.Len()
	rnd := rand.Intn(n)
	return deck.cards[rnd]
}

// WantToCut returns true if the player wishes to cut
func (p *Player) WantToCut() bool {
	return rand.Float64() > 0.5
}

// WantToReshuffle returns true if the player wishes to shuffle again
func (p *Player) WantToReshuffle() bool {
	return rand.Float64() > 0.5
}
