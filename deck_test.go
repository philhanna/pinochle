package pinochle

import (
	"fmt"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func printDeck(label string, cards []Card, denom... int) {
	fmt.Printf("%s:\n", label)
	if len(denom) == 0 {
		denom = []int{4}
	}
	buffer := make([]string, 0)
	n := len(cards) / denom[0]
	for _, card := range cards {
		buffer = append(buffer, card.Unicode())
		if len(buffer) == n {
			fmt.Printf("%s\n", strings.Join(buffer, " "))
			buffer = buffer[0:0]
		}
	}
}
func TestDeck(t *testing.T) {
	deck := NewDeck()
	printDeck("New pinochle deck", deck.cards)
}

func TestDeck_Shuffled(t *testing.T) {
	deck := NewDeck()
	deck.Shuffle()
	printDeck("New pinochle deck", deck.cards)
}

func TestDeck_ShuffledThenSorted(t *testing.T) {
	deck := NewDeck()
	deck.Shuffle()
	deck.Sort()
	printDeck("New pinochle deck", deck.cards)
}

func TestDeck_Remove(t *testing.T) {
	tests := []struct {
		name    string
		d       Deck
		c       Card
		want    bool
		newDeck Deck
	}{
		{
			name: "Happy path",
			d: Deck{
				[]Card{
					NewCard(ACE, SPADES),
					NewCard(KING, CLUBS),
					NewCard(KING, DIAMONDS),
					NewCard(ACE, CLUBS),
				},
			},
			c:    NewCard(ACE, SPADES),
			want: true,
			newDeck: Deck{
				[]Card{
					NewCard(KING, CLUBS),
					NewCard(KING, DIAMONDS),
					NewCard(ACE, CLUBS),
				},
			},
		},
		{
			name: "Card not in deck",
			d: Deck{
				[]Card{
					NewCard(ACE, SPADES),
					NewCard(KING, CLUBS),
					NewCard(KING, DIAMONDS),
					NewCard(ACE, CLUBS),
				},
			},
			c:    NewCard(ACE, HEARTS),
			want: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			startingLength := len(tt.d.cards)
			want := tt.want
			have := tt.d.Remove(tt.c)
			assert.Equal(t, want, have)
			endingLength := len(tt.d.cards)
			if want {
				assert.Equal(t, startingLength, endingLength+1)
			} else {
				assert.Equal(t, startingLength, endingLength)
			}
		})
	}
}

func TestDeck_Sort(t *testing.T) {
	var (
		TEN_OF_SPADES = NewCard(TEN, SPADES)
		JACK_OF_CLUBS = NewCard(JACK, CLUBS)
		ACE_OF_HEARTS = NewCard(ACE, HEARTS)
	)
	deck := Deck{[]Card{TEN_OF_SPADES, JACK_OF_CLUBS, ACE_OF_HEARTS}}
	deck.Sort()
	assert.Equal(t, deck.cards[0], JACK_OF_CLUBS)
	assert.Equal(t, deck.cards[1], TEN_OF_SPADES)
	assert.Equal(t, deck.cards[2], ACE_OF_HEARTS)
}
