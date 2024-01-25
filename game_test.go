package pinochle

import (
	"fmt"
	"testing"

	"github.com/stretchr/testify/assert"
)

var (
	LARRY = &Player{Name: "Larry"}
	CURLY = &Player{Name: "Curly"}
	MOE   = &Player{Name: "Moe"}
	SHEMP = &Player{Name: "Shemp"}
)

func getTestGame() *Game {
	game := Game{
		Players: [4]*Player{LARRY, CURLY, MOE, SHEMP},
		NSTeam:  Team{Players: [2]*Player{LARRY, MOE}},
		EWTeam:  Team{Players: [2]*Player{CURLY, SHEMP}},
	}
	return &game
}

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
			game: *getTestGame(),
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

func TestGame_PlayerOnLeft(t *testing.T) {
	tests := []struct {
		name   string
		game   *Game
		player *Player
		want   *Player
	}{
		{name: "1st player", game: getTestGame(), player: LARRY, want: CURLY},
		{name: "2nd player", game: getTestGame(), player: CURLY, want: MOE},
		{name: "3rd player", game: getTestGame(), player: MOE, want: SHEMP},
		{name: "4th player", game: getTestGame(), player: SHEMP, want: LARRY},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			other := tt.game.PlayerOnLeft(tt.player)
			assert.Equal(t, tt.want, other)
		})
	}
}

func TestGame_PlayerOnRight(t *testing.T) {
	tests := []struct {
		name   string
		game   *Game
		player *Player
		want   *Player
	}{
		{name: "1st player", game: getTestGame(), player: LARRY, want: SHEMP},
		{name: "2nd player", game: getTestGame(), player: CURLY, want: LARRY},
		{name: "3rd player", game: getTestGame(), player: MOE, want: CURLY},
		{name: "4th player", game: getTestGame(), player: SHEMP, want: MOE},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			other := tt.game.PlayerOnRight(tt.player)
			assert.Equal(t, tt.want, other)
		})
	}
}
