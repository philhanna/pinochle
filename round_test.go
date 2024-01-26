package pinochle

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestNewRound(t *testing.T) {
	var (
		frodo   = &Player{Name: "Frodo"}
		sam     = &Player{Name: "Sam"}
		gollum  = &Player{Name: "Gollum"}
		gandalf = &Player{Name: "Gandalf"}
	)
	tests := []struct {
		name   string
		game   *Game
		dealer *Player
		live   bool
	}{
		{
			name: "Happy path",
			game: &Game{
				Players: [4]*Player{frodo, sam, gollum, gandalf},
			},
			dealer: gollum,
			live:   true,
		},
		{
			name: "Force reshuffle",
			game: &Game{
				Players: [4]*Player{frodo, sam, gollum, gandalf},
			},
			dealer: gollum,
			live:   false,
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
			for _, player := range tt.game.Players {
				player.Hand.Sort()
				printDeck(player.Name, player.Hand, 1)
			}
		})
	}
}
