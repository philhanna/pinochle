# Pinochle

This application supports playing Pinochle on the Web.
There is a server-side component written in Python.
Each player sees a front-end component written in JavaScript or TypeScript

## Actors

- Player
    - Four in number.
    - Each can be either human or computer.
    - The players form two teams consisting of players across the table
      from each other.

- Administrator
    - Can also be one of the players.
    - Sets up the game
    - Specifies the players
    - Initiate play

## Interactions

Each player sees the layout of the playing table with themselves at the
bottom.  The player can see his own cards, but only the card backs of
the other players.

Play proceeds according to the usual rules, clockwise around the table.

## Dealer selection

At the beginning of the game, all four players select a card from a
spread-out face-down deck.  The player with the highest card becomes the
dealer.  In case of a tie, the process is repeated.

## Play a round

The deck is shuffled, then dealt three cards at a time starting with the
player to the left of the dealer.  The player sees his own cards
ordered descending by suit then card rank.

## Bidding

Starting with the player on the dealer's left, each player announces his
bid or pass.  Bids must be divisible by 10. The starting bid must be >=
250.  Each subsequent bid must be >= the previous bid. If all four pass,
the round is over and the next round begins (return to "Play a round").
If the first player bid but all three others passes, the player has the
option of declining to play, and the round is similarly over.  When
three players have passed, the remaining player wins the auction and
declares the trump suit.

## Passing cards

The partner of the auction winner passes his partner four cards from his
own hand.  The cards can be seen by the auction winner's team but not the
opposing team.  The cards are added to the auction winner's hand.  Then
he select four cards from that hand and passes them back to his partner

## Meld

The meld of each player is exposed on the table in front of them, and
the totals are displayed.

## Taking tricks

The auction winner lays down a card.  Each player in turn clockwise
plays a card.  Each player must follow suit if he can, and must beat the
card if he can.  If the player has no cards of that suit, he must play a
trump if he has it.  He must beat the currently high card played in this
trick.  After all four players have played a card, the team who played
the winning card wins the trick and collects all four cards.  He then
become the player who leads first for the next trick.  Play continues
until all four players have played all their cards.

## Assessing the round

The total points for each team is summed.  This includes their meld and
the points accumulated from taking tricks (plus 10 point for the last
trick).  If the auction winning team has a total >= their bid, they are
said to have won the round and their total for this round is added to
their grand total.  If they failed to have total >= their bid, they are
said to have "gone set" and their grand total has the amount of their
bid subtracted.  The other team has the amount of their meld plus the
point value of their tricks taken added to their grand total, unless
they failed to win any tricks.

If either team has exceeded a grand total of 2000 points, the game is
over and they have won (if both have passed 2000, the auction winner of
the just-completed round wins).  Otherwise, another round is played.  Go
back to "Play a round".

## Visuals

The screen reproduces as closely as possible what a player would
actually see in a live game:

- A background of green, like the green felt of a pool table
- The player names at North, South, East, and West
- Their hands with the backs of the cards visible, fanned out somewhat
- An area in the middle where tricks are played, with each player's
  card closer to them so that all four cards can be seen

When it is a player's turn, they make their moves
by dragging cards to the center of the table.  As soon as
they have done this, the other three players can see the card.

This implies that the browsers for each player should
- show the game only from the player's standpoint
- refresh the display when a play has been made
- receive push notifications rather than polling

