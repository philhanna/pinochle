package pinochle

// ---------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------

// Game is a server that coordinates the actions of the players and the
// games.
type Game struct {
	Players [4]*Player
	NSTeam  *Team
	EWTeam  *Team
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
		card1 := cards[0]
		card2 := cards[1]
		switch {
		case card1.Rank.Less(card2.Rank):
			return &card2
		case card2.Rank.Less(card1.Rank):
			return &card1
		default:
			return nil
		}
	default: // More than 2 cards
		deck := Deck{cards}
		deck.Sort()
		n := deck.Len()
		lastCard := deck.cards[n-1]
		nextToLastCard := deck.cards[n-2]
		if lastCard.Rank == nextToLastCard.Rank {
			return nil // Tie
		}
		return &lastCard
	}
}
