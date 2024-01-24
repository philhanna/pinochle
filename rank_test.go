package pinochle

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestRank_String(t *testing.T) {
	tests := []struct {
		name string
		r    Rank
		want string
	}{
		{"numbered card", FIVE, "5"},
		{"Jack", JACK, "J"},
		{"Queen", QUEEN, "Q"},
		{"King", KING, "K"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			want := tt.want
			have := tt.r.String()
			assert.Equal(t, want, have)
		})
	}
}
