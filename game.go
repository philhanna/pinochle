package pinochle

// ---------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------

// Game is a server that coordinates the actions of the players and the
// games.
type Game struct {
	Players [4]*Player
	NSTeam  Team
	EWTeam  Team
}

// ---------------------------------------------------------------------
// Functions
// ---------------------------------------------------------------------

// CardWithHighestRank returns a pointer to the card with the highest
// rank.  If there is a tie, returns nil.
func CardWithHighestRank(cards []Card) *Card {
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

// ---------------------------------------------------------------------
// Methods
// ---------------------------------------------------------------------

// ChooseDealer chooses the dealer for the first round. This requires
// interaction with each player, who chooses a card from the deck. The
// highest card drawn determintes the dealer. In case of a tie, the
// players choose again at random.
//
// In subsequent rounds, the dealer is the player on the previous
// dealer's left.
func (g *Game) ChooseDealer() *Player {

	var dealer *Player
	for {
		cardChoice := make(map[*Player]Card)
		deck := NewDeck()
		for _, player := range g.Players {
			card := player.DrawCard(deck)
			cardChoice[player] = card
			deck.Remove(card)
		}
		cards := make([]Card, 0)
		for _, card := range cardChoice {
			cards = append(cards, card)
		}
		highCard := CardWithHighestRank(cards)
		if highCard != nil {
			for player, card := range cardChoice {
				if card == *highCard {
					dealer = player
				}
			}
			break
		}
	}
	return dealer
}

// PlayerOnLeft returns the player to the left of the specified player
func (g *Game) PlayerOnLeft(p *Player) *Player {
	var other *Player
	for i := 0; i < len(g.Players); i++ {
		if g.Players[i] == p {
			j := i + 1
			if j >= len(g.Players) {
				j -= len(g.Players)
			}
			other = g.Players[j]
		}
	}
	return other
}

// PlayerOnRight returns the player to the right of the specified player
func (g *Game) PlayerOnRight(p *Player) *Player {
	var other *Player
	for i := 0; i < len(g.Players); i++ {
		if g.Players[i] == p {
			j := i - 1
			if j < 0 {
				j += len(g.Players)
			}
			other = g.Players[j]
		}
	}
	return other
}
