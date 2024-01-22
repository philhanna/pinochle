package pinochle

// ---------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------

// Game is a server that coordinates the actions of the players and the
// games. 
type Game struct {
	Players [4]*Player
	NSTeam *Team
	EWTeam *Team
}
