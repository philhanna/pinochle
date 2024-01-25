package pinochle

import (
	"fmt"
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
		{"Ace of spades", NewCard(ACE, SPADES), `sodipodi:docname="spades_ace_simple.svg"`, false},
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
		{"Nine of clubs", NewCard(NINE, CLUBS), "9" + string('\u2663')},
		{"Ten of diamonds", NewCard(TEN, DIAMONDS), "10" + string('\u2662')},
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

func TestCard_Unicode(t *testing.T) {
	tests := []struct {
		name string
		card Card
		want string
	}{
		{
			name: "Jack of hearts",
			card: NewCard(JACK, HEARTS),
			want: fmt.Sprintf("%c", 0x1f0bb      ),
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			assert.Equal(t, tt.want, tt.card.Unicode())
		})
	}
}
