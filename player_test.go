package pinochle

import (
	"fmt"
	"testing"
)

func TestPlayer_WantToReshuffle(t *testing.T) {
	const limit = 100
	var (
		nHeads int
		nTails int
	)
	player := new(Player)
	for i := 0; i < limit; i++ {
		if player.WantToReshuffle() {
			nHeads++
		} else {
			nTails++
		}
	}
	fmt.Printf("nHeads=%d, nTails=%d\n", nHeads, nTails)
}

func TestPlayer_WantToCut(t *testing.T) {
	const limit = 100
	var (
		nHeads int
		nTails int
	)
	player := new(Player)
	for i := 0; i < limit; i++ {
		if player.WantToCut() {
			nHeads++
		} else {
			nTails++
		}
	}
	fmt.Printf("nHeads=%d, nTails=%d\n", nHeads, nTails)
}
