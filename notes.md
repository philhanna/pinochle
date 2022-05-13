## Client behavior

### Player
At some point, each of these need to be done:
- Pass the server the player name
- Make a bid (or pass)
- Choose trump
- Pass cards to partner
- Make meld
- Select card to play (repeat until done)

### Administrator
- Select partners for players
- Start a game
- Update score

### Design issues
So how does the round of play proceed?  The server doesn't "push".
When a player makes a move, the "current player" property needs to be updated.
How is this shown to the players?  Some kind of console?  But what
causes the player web pages to be updated?
