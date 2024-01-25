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
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			round := NewRound(tt.game, tt.dealer)
			assert.NotNil(t, round)
			assert.Equal(t, tt.dealer, round.dealer)
		})
	}
}
