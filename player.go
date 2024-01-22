package pinochle

// Player is one of the four participants in the game.
type Player struct {
	ID       string
	Name     string
	Position uint8
	TeamID   string
}

type HumanPlayer struct {
	Player
	Host string
	Port int
}

type ComputerPlayer struct {
	Player
}
