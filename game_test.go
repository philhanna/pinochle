package pinochle

import (
	"fmt"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestHighestRank(t *testing.T) {
	var (
		TEN_OF_DIAMONDS = NewCard(TEN, DIAMONDS)
		TEN_OF_HEARTS   = NewCard(TEN, HEARTS)
		KING_OF_SPADES  = NewCard(KING, SPADES)
		JACK_OF_SPADES  = NewCard(JACK, SPADES)
		NINE_OF_HEARTS  = NewCard(NINE, HEARTS)
		NINE_OF_CLUBS   = NewCard(NINE, CLUBS)
	)

	tests := []struct {
		name  string
		cards []Card
		want  *Card
	}{
		{
			name:  "Empty",
			cards: []Card{},
		},
		{
			name: "Happy path - clear winner",
			cards: []Card{
				KING_OF_SPADES,
				JACK_OF_SPADES,
				NINE_OF_HEARTS,
				TEN_OF_DIAMONDS,
			},
			want: &TEN_OF_DIAMONDS,
		},
		{
			name: "Tie - two tens",
			cards: []Card{
				KING_OF_SPADES,
				TEN_OF_HEARTS,
				NINE_OF_HEARTS,
				TEN_OF_DIAMONDS,
			},
		},
		{
			name: "Tie but in lower cards",
			cards: []Card{
				KING_OF_SPADES,
				NINE_OF_HEARTS,
				NINE_OF_CLUBS,
				TEN_OF_DIAMONDS,
			},
			want: &TEN_OF_DIAMONDS,
		},
		{
			name:  "Only one card",
			cards: []Card{TEN_OF_DIAMONDS},
			want:  &TEN_OF_DIAMONDS,
		},
		{
			name: "Only two cards",
			cards: []Card{
				NINE_OF_HEARTS,
				TEN_OF_DIAMONDS,
			},
			want: &TEN_OF_DIAMONDS,
		},
		{
			name: "Only two cards, first is higher",
			cards: []Card{
				JACK_OF_SPADES,
				NINE_OF_HEARTS,
			},
			want: &JACK_OF_SPADES,
		},
		{
			name: "Only two cards but tie",
			cards: []Card{
				NINE_OF_HEARTS,
				NINE_OF_CLUBS,
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			want := tt.want
			have := CardWithHighestRank(tt.cards)
			assert.Equal(t, want, have)
		})
	}
}

func TestGame_ChooseDealer(t *testing.T) {
	tests := []struct {
		name string
		game Game
	}{
		{
			name: "Happy path",
			game: Game{
				Players: [4]*Player{
					{Name: "Larry"},
					{Name: "Curly"},
					{Name: "Moe"},
					{Name: "Shemp"},
				},
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			player := tt.game.ChooseDealer()
			fmt.Printf("Dealer is %q\n", player.Name)
			assert.NotNil(t, player)
		})
	}
}
