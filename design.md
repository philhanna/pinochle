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
- [Phases of the game](#phases)
  1. [Setting up teams and players](#1-setting-up-teams-and-players)
  2. [Choosing the detaler](#2-choosing-the-dealer)
  3. [Hand](#3-hand)
  4. [Bidding](#4-bidding)
  5. [Setting up the contract](#5-set-up-contract)
  6. [Melding](#6-melding)
  7. [Playing the hand](#7-play-the-hand)
  8. [Scoring the round](#8-scoring-the-round)

<a id="overview"></a>
## Overview
This is a design for a web-based pinochle game for four players.
Each player can be either a human or a computer.

See [pinochle-game-rules](https://playingcarddecks.com/blogs/how-to-play/pinochle-game-rules)

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

<hr/>

### Game
Game is a server that coordinates the actions of the players and the games.
The first team to reach 2000 points wins the game.

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
- Player type (human or computer)
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

<a id="phases"></a>
## Phases of the game

<a id="1-setting-up-teams-and-players"></a>
### 1. Setting up teams and players
There needs to be two teams of two players each, any combination of
human or computer players.  The players need to be registered and
assigned to teams.

- **Admin** starts **MainServer**
- **MainServer** listens for connections from players and accepts them as pending players.
- **Admin** adds computer player(s) as pending players.
- **Admin** assigns teams.
- **Admin** assigns players to teams
- **Admin** starts each **PlayerServer**
- **Admin** tells **MainServer** to shuffle the deck
- **Admin** starts the game by sending each **PlayerServer** a message saying the game
has started.

[Back to top]

<a id="2-choosing-the-dealer"></a>
### 2. Choosing the dealer
The players each choose a card. If there is a highest rank among the
four cards, the player holding that card is the dealer.  Otherwise, the
players return their cards to the deck and choose new cards.  Repeat
until a dealer is selected.

- Each **Player** issues a GET request to **MainServer** to get a random card from the deck,
- **MainServer** keeps track of which card is chosen by each **Player**
- After all four players have selected a card, **MainServer** compare them to see
which is the greatest.  If there is a highest rank, **MainServer** sends a notification
to each **Player** announcing the winning player.  Otherwise, it sends a notification
asking each **Player** to select another card.
- This continues until a dealer has been selected.

[Back to top]

<a id="3-hand"></a>
### 3. Hand
The dealer shuffles as many times as they desire (but at least once).
The player to the dealer's right has the option to cut the cards.  Then
the dealer deals three cards at a time to each player, starting with the
player on their left and proceeding clockwise until the deck is empty.

[Back to top]

<a id="4-bidding"></a>
### 4. Bidding
The player to the dealer makes the first bid, which must be either pass
or a multiple of 10 greater than or equal to 250. Each player in turn
either passes or makes a bid of a multiple of 10 greater than the previous
bid.  A player that has passed no longer participates in this round of
bidding.  When there is no more than one player who has not passes,
that player becomes the contract winner.

- If no player has bid, the hand is over and another one is started,
with the player to the dealer's left becoming the dealer (go back to
step 3)

- If only one player has made an opening bid and everyone else has passed,
the bidding player has the option to play the hand or throw it in.
If the hand is thrown in, another one is started, with the player at
the dealer's left becoming the dealer (go back to step 3).

[Back to top]

<a id="5-set-up-contract"></a>
### 5. Setting up the contract
The player who won the bid announces the trump suit.
Their partner then passes them four cards
and receives four cards from the bid winner.

[Back to top]

<a id="6-melding"></a>
### 6. Melding
Each player lays down their meld.  Meld consists of any of the following:

| Name | Contents | Scoring value |
| ---- | -------- | ------------- |
| Run | A, 10, K, Q, J of trump | 150 |
| 100 Aces | An ace from each suit | 100 |
| 80 Kings | A king from each suit | 80 |
| 60 Queens | A queen from each suit | 60 |
| 40 Jacks | A jack from each suit | 40 |
| Royal marriage | K and Q of trump | 40 |
| Marriage | K and Q of non-trump suit | 20 |
| Pinochle | Q♤ and J♦ | 40 |
| Trump nine | A 9 of trump | 10 |
| Double run | Two A, 10, K, Q, J of trump | 1500 |
| 1000 Aces | All 8 aces in the deck | 1000 |
| 800 Kings | All 8 kings in the deck | 800 |
| 600 Queens | All 8 queens in the deck | 600 |
| 400 Jacks | All 8 jacks in the deck | 400 |
| Double pinochle | Two Q♤ and two J♦ | 300 |

Cards can be shared between any other units of meld in the hand.
For example, the cards K♤,  Q♤ and J♦ counts as both a marriage
and a pinochle.

The total meld of each team is provisionally added to their
total score.

[Back to top]

<a id="7-play-the-hand"></a>
### 7. Playing the hand

- Starting with the bid winner, each player lays down a card.
- Going clockwise, each player lays down a card, playing a higher card
  if they are able. A higher card is defined as a card of the same suit
  as the first card played by the bid winner that has a higher rank than
  any other of that suit played, or a trump card of a higher rank than
  any other trump card.
- If the player can follow suit, they must do so.
- If they have no cards of that suit, they must trump if they are able.
- Otherwise, they can play any other card.

Whoever played the highest card of the four wins the trick and collects
all four cards.  That person plays the first card of the next trick.

Play continues until the last card from each hand has been played.

<hr/>

<a id="8-score-the-round"></a>

### 8. Scoring the round
Each team counts cards from all the tricks they took.  They are scored as follows:
- Aces and Tens count as 10 points each
- Kings and Queens count as 5 points each
- Last trick counts as 10 points.

If the team that won the bid has greater than or equal to the points they bid
(including their meld), they have won the bid.

If not, the team that won the bid loses the value of their meld and the value
of their contract.  This is referred to as "going set".

Regardless, the team that did not win the bid keeps their meld, unless they
took no tricks at all.

The scoring value for each team this round is added to their cumulative
score.  If either team meets or exceeds 2000 points, they are the winner and the
game is over.  If both teams meet or exceed 2000 points, the team that won the bid
is the winner and the game is over.

If neither team met or exceeded a score of 2000, the game continues
with the player to the dealer's left becoming the next dealer.
(Go back to step 3).

[Back to top]


[Back to top]: #top
