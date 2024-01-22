package pinochle

// ---------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------

// Team is a pair of partners
type Team struct {
	ID      string
	Name    string
	Score   int
	Players [2]*Player
}
