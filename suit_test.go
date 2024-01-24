package pinochle

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestSuit_iterate(t *testing.T) {
	for i, suit := range Suits {
		switch i {
		case 0:
			assert.Equal(t, suit, SPADES)
		case 1:
			assert.Equal(t, suit, HEARTS)
		case 2:
			assert.Equal(t, suit, DIAMONDS)
		case 3:
			assert.Equal(t, suit, CLUBS)
		}
	}
}

func TestSuit_Glyph(t *testing.T) {
	tests := []struct {
		name string
		suit Suit
		want string
	}{
		{"Hearts", HEARTS, string('\u2661')},
		{"Clubs", CLUBS, string('\u2663')},
		{"Diamonds", DIAMONDS, string('\u2662')},
		{"Spades", SPADES, string('\u2660')},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			want := tt.want
			have := tt.suit.Glyph()
			assert.Equal(t, want, have)
		})
	}
}

func TestSuit_Character(t *testing.T) {
	tests := []struct {
		name string
		suit Suit
		want string
	}{
		{"Hearts", HEARTS, "H"},
		{"Clubs", CLUBS, "C"},
		{"Diamonds", DIAMONDS, "D"},
		{"Spades", SPADES, "S"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			want := tt.want
			have := tt.suit.Character()
			assert.Equal(t, want, have)
		})
	}
}

func TestSuit_String(t *testing.T) {
	tests := []struct {
		name string
		os   string
		suit Suit
		want string
	}{
		{
			name: "hearts",
			os:   "Linux",
			suit: HEARTS,
			want: "\u2661",
		},
		{
			name: "hearts on windows",
			os:   "Windows",
			suit: HEARTS,
			want: "H",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			want := tt.want
			if tt.os == "Windows" {
				ISWINDOWS = func() bool { return true }
			} else {
				ISWINDOWS = func() bool { return false }
			}
			have := tt.suit.String()
			assert.Equal(t, want, have)
		})
	}
}
