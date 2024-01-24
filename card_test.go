package pinochle

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCard_GetSVG(t *testing.T) {
	tests := []struct {
		name    string
		card    Card
		want    string
		wantErr bool
	}{
		{"Three of clubs", NewCard(THREE, CLUBS), `sodipodi:docname="clubs_3.svg"`, false},
		{"Ace of spades", NewCard(ACE, SPADES), `sodipodi:docname="spades_ace_simple.svg"`, false},
		{"2 of diamonds", NewCard(TWO, DIAMONDS), `sodipodi:docname="diamonds_2.svg`, false},
		{"4 of hearts", NewCard(FOUR, HEARTS), `sodipodi:docname="hearts_4.svg`, false},
		{"Jack of spades", NewCard(JACK, SPADES), `sodipodi:docname="spades_jack.svg"`, false},
		{"Queen of spades", NewCard(QUEEN, SPADES), `sodipodi:docname="spades_queen.svg"`, false},
		{"King of hearts", NewCard(KING, HEARTS), `sodipodi:docname="hearts_king.svg"`, false},
		{"bogus", Card{}, "", true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			c := tt.card
			have, err := c.GetSVG()
			if tt.wantErr {
				assert.NotNil(t, err)
				return
			}
			assert.Nil(t, err)
			assert.Contains(t, have, tt.want)
		})
	}
}

func TestCard_String(t *testing.T) {
	tests := []struct {
		name string
		card Card
		want string
	}{
		{"Three of clubs", NewCard(THREE, CLUBS), "3" + string('\u2663')},
		{"Ace of spaces", NewCard(ACE, SPADES), "A" + string('\u2660')},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			want := tt.want
			have := tt.card.String()
			assert.Equal(t, want, have)
		})
	}
}
