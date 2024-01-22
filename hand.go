package pinochle

import "github.com/philhanna/cards"

type Hand struct {
	BidWinner *Player
	Trump     cards.Suit
}
