<style>
    body {
        font-size: 110%;
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
    - [Cards](#cards)
    - [Game](#game)
    - [Team](#team)
    - [Player](#player)
    - [Hand](#hand)
- [Interactions](#interactions)
  - [Setting up teams and players](#setting-up-teams-and-players)
  - [Choosing the detaler](#choosing-the-dealer)
  - [Deal](#deal)

<a id="overview"></a>
## Overview
This is a design for a web-based pinochle game for four players.
Each player can be either a human or a computer.

[Back to top]
<hr/>

<a id="classes"></a>
## Classes
The classes used include `Cards`, `Game`, `Team`, `Player`, `Hand`.

[Back to top]
<hr/>

<a id="cards"></a>

### Cards

<a id="game"></a>
The cards and associated classes come from the [cards library](https://github.com/philhanna/cards)
and include:

- Suit - SPADES, HEARTS, DIAMONDS, and CLUBS.
- Rank - 2 through Ace, with ordering functions to handle regular and pinochle decks.
- Card - A combination of Rank and Suit. The library contains SVG images for each card.
- PinochleDeck - A collection of Cards for a 48-card Pinochle deck.

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
- Start a round.

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

<a id="interactions"></a>
## Interactions

<a id="setting-up-teams-and-players"></a>
### 1. Setting up teams and players
There needs to be two teams of two players each, any combination of
human or computer players.  The players need to be registered and
assigned to teams.

<a id="choosing-the-dealer"></a>
### 2. Choosing the dealer
The players each choose a card. If there is a highest rank among the
four cards, the player holding that card is the dealer.  Otherwise, the
players return their cards to the deck and choose new cards.  Repeat
until a dealer is selected.

<a id="deal"></a>
### 3. Deal
The dealer shuffles as many times as they desire.  The player to the
dealer's right has the option to cut the cards.  Then the dealer
deals three cards at a time to each player, starting with the player
on their left and proceeding clockwise until the deck is empty.

[Back to top]

[Back to top]: #top
