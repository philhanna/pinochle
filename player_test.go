package pinochle

import (
	"testing"
)

type mockFlipper struct {
	timesCalled int
}

func (m *mockFlipper) flip() bool {
	m.timesCalled++
	if m.timesCalled < 3 {
		return true
	}
	m.timesCalled = 0
	return false
}

func TestPlayer_WantToReshuffle(t *testing.T) {

	tests := []struct {
		name string
		live bool
	}{
		{
			name: "Live",
			live: true,
		},
		{
			name: "Mocked",
			live: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			player := new(Player)
			if tt.live {
				for i := 0; i < 10; i++ {
					player.WantToReshuffle()
				}
			} else {
				flipper := new(mockFlipper)
				COIN_FLIP = flipper.flip
				for i := 0; i < 10; i++ {
					player.WantToReshuffle()
				}
				COIN_FLIP = DEFAULT_COIN_FLIP

			}
		})
	}
}

func TestPlayer_WantToCut(t *testing.T) {
}
