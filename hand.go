package pinochle

import "sort"

// ---------------------------------------------------------------------
// Type definitions
// ---------------------------------------------------------------------

type Hand []Card

// Sort reorders the cards of the hand by suit and rank
func (h *Hand) Sort() {
	sort.Slice([]Card(*h), func(i, j int) bool {
		cards := []Card(*h)
		iCard := cards[i]
		jCard := cards[j]
		switch {
		case iCard.Suit < jCard.Suit:
			return true
		case iCard.Suit > jCard.Suit:
			return false
		case iCard.Rank < jCard.Rank:
			return true
		case iCard.Rank > jCard.Rank:
			return false
		default:
			return false
		}
	})
}