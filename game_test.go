package pinochle

import (
	"testing"

	"github.com/philhanna/cards"
	"github.com/stretchr/testify/assert"
)

func TestHighestRank(t *testing.T) {
	var (
		TEN_OF_DIAMONDS = cards.NewCard(cards.TEN, cards.DIAMONDS)
		TEN_OF_HEARTS   = cards.NewCard(cards.TEN, cards.HEARTS)
		KING_OF_SPADES  = cards.NewCard(cards.KING, cards.SPADES)
		JACK_OF_SPADES  = cards.NewCard(cards.JACK, cards.SPADES)
		NINE_OF_HEARTS  = cards.NewCard(cards.NINE, cards.HEARTS)
		NINE_OF_CLUBS   = cards.NewCard(cards.NINE, cards.CLUBS)
	)

	tests := []struct {
		name  string
		cards []cards.Card
		want  *cards.Card
	}{
		{
			name:  "Empty",
			cards: []cards.Card{},
		},
		{
			name: "Happy path - clear winner",
			cards: []cards.Card{
				KING_OF_SPADES,
				JACK_OF_SPADES,
				NINE_OF_HEARTS,
				TEN_OF_DIAMONDS,
			},
			want: &TEN_OF_DIAMONDS,
		},
		{
			name: "Tie - two tens",
			cards: []cards.Card{
				KING_OF_SPADES,
				TEN_OF_HEARTS,
				NINE_OF_HEARTS,
				TEN_OF_DIAMONDS,
			},
			want: nil,
		},
		{
			name: "Tie but in lower cards",
			cards: []cards.Card{
				KING_OF_SPADES,
				NINE_OF_HEARTS,
				NINE_OF_CLUBS,
				TEN_OF_DIAMONDS,
			},
			want: &TEN_OF_DIAMONDS,
		},
		{
			name:  "Only one card",
			cards: []cards.Card{TEN_OF_DIAMONDS},
			want:  &TEN_OF_DIAMONDS,
		},
		{
			name: "Only two cards",
			cards: []cards.Card{
				NINE_OF_HEARTS,
				TEN_OF_DIAMONDS,
			},
			want: &TEN_OF_DIAMONDS,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			want := tt.want
			have := HighestRank(tt.cards)
			assert.Equal(t, want, have)
		})
	}
}
