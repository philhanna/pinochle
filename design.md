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
    - [Player](#player)
    - [Team](#team)
    - [Game](#game)
    - [Hand](#hand)

<a id="overview"></a>
## Overview
This is a design for a web-based pinochle game for four players.
Each player can be either a human or a computer.

[Back to top]

<a id="classes"></a>
## Classes
The classes used include `Player`, `Team`, `Game`, `Hand`

[Back to top]

<hr/>

<a id="player"></a>
### Player

There are exactly four players, two pairs of partners.
#### Attributes

- Player ID
- Player name
- Team ID
- Host name
- Port number

<hr/>

<a id="team"></a>
### Team
A team is a pair of partners.

#### Attributes

- Team name (e.g., "Men", "Women", etc.)
- Team ID
- Cumulative score for this team

<hr/>

<a id="game"></a>
### Game
Game is a server that coordinates the actions of the players and the games.

#### Attributes

- Player names and positions (0, 1, 2, 3)
- Team N/S
- Team E/W

<hr/>

<a id="hand"></a>
### Hand
Hand is one round of play

#### Attributes
- Bid winner
- Trump suit

#### Actions
- Deal
- Round of bidding
- Passing four cards from bid winner to partner
- Passing four cards from partner to bid winner

[Back to top]: #top
