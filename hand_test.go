package pinochle

import "testing"

func TestHand_Sort(t *testing.T) {
	tests := []struct {
		name string
		hand Hand
	}{
		{
			name: "basic",
			hand: func() Hand {
				deck := NewDeck()
				deck.Shuffle()
				hand := deck.cards[:12]
				return hand
			}(),
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tt.hand.Sort()
			printDeck("Sorted hand", tt.hand, 1)
		})
	}
}
