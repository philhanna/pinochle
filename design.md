<style>
    body {
        font-size: 130%;
    }
    li {
        line-height: 1.5em;
    }
</style>

<a id="top"></a>
# Design notes for pinochle game
<style>
ul {
    line-height: 1.0
}
</style>

## Table of contents
- [Overview](#overview)
- [Classes](#classes)
    - [Game](#game)
    - [Team](#team)
    - [Player](#player)
    - [Hand](#hand)

<a id="overview"></a>
## Overview
This is a design for a web-based pinochle game for four players.
Each player can be either a human or a computer.

[Back to top]
<hr/>

<a id="classes"></a>
## Classes
The classes used include `Game`, `Team`, `Player`, `Hand`.

[Back to top]
<hr/>

<a id="game"></a>

### Game
Game is a server that coordinates the actions of the players and the games.

#### Attributes
- Array of player IDs for positions (0, 1, 2, 3)
- Team ID N/S
- Team ID E/W

#### Actions
- Choose the dealer. This requires interaction with each player, who chooses a card
from the deck.  The highest card drawn determintes the dealer.  In case of a tie,
the players choose again at random.

[Back to top]
<hr/>

<a id="team"></a>

### Team
A team is a pair of partners.

#### Attributes
- Team ID
- Team name (e.g., "Men", "Women", etc.)
- Cumulative score in this game for this team

#### Actions

[Back to top]
<hr/>

<a id="player"></a>

### Player
There are exactly four players, two pairs of partners.

#### Attributes
- Player ID
- Player name
- Position (0, 1, 2, 3) = North, East, South, West
- Team ID
- Host name
- Port number

#### Actions
[Back to top]
<hr/>

<a id="hand"></a>

### Hand
Hand is one round of play

#### Attributes
- Bid winner
- Trump suit

#### Actions
- Shuffle the cards
- Deal
- Round of bidding
- Passing four cards from bid winner to partner
- Passing four cards from partner to bid winner

[Back to top]
<hr/>

[Back to top]: #top
