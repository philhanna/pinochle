package pinochle

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestNewRound(t *testing.T) {
	tests := []struct {
		name   string
		game   *Game
		dealer *Player
		live   bool
	}{
		{
			name: "Happy path",
			game: &Game{
				Players: [4]*Player{
					{Name: "Frodo"},
					{Name: "Sam"},
					{Name: "Gollum"},
					{Name: "Gandalf"},
				},
			},
			dealer: &Player{Name: "Gollum"},
			live: true,
		},
		{
			name: "Force reshuffle",
			game: &Game{
				Players: [4]*Player{
					{Name: "Frodo"},
					{Name: "Sam"},
					{Name: "Gollum"},
					{Name: "Gandalf"},
				},
			},
			dealer: &Player{Name: "Gollum"},
			live: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if !tt.live {
				mockFlipper := new(mockFlipper)
				COIN_FLIP = mockFlipper.flip
			}
			defer func() {
				COIN_FLIP = DEFAULT_COIN_FLIP
			}()
			round := NewRound(tt.game, tt.dealer)
			assert.NotNil(t, round)
			assert.Equal(t, tt.dealer, round.dealer)
		})
	}
}
