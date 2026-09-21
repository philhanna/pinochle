# Pinochle — Requirements

**Status:** Draft
**Last updated:** 2026-09-06

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for a
web-based, four-player Pinochle game. It is the authoritative statement of
*what* the system must do. It deliberately avoids prescribing *how*, except
where an architectural constraint is itself a requirement (see §4).

### 1.2 Scope

The system consists of:

- A **server-side application** written in Python that owns all game state and
  enforces all rules.
- A **browser-based client** written in JavaScript or TypeScript, one instance
  per human player, that renders the table from that player's point of view and
  submits that player's actions.
- **Computer players** that can occupy any of the four seats and are driven by
  the server.

Out of scope for the first release: user accounts and persistent player
profiles, matchmaking/lobbies beyond a single administrator-created game,
ranking or statistics, chat, and mobile-native clients.

### 1.3 Definitions

| Term | Meaning |
| --- | --- |
| **Game** | A complete contest, played over multiple rounds, until a team reaches the winning score. |
| **Round** | One deal: dealer selection is excluded; comprises deal → bid → trump → pass → meld → trick play → scoring. |
| **Trick** | One cycle in which each of the four players plays exactly one card. |
| **Meld** | Scoring card combinations held in hand and exposed after the pass, before trick play. |
| **Contract** | The winning bid amount that the bidding team must meet or exceed. |
| **Going set** | Failing to make the contract. |
| **Trump** | The suit named by the bid winner, which outranks all other suits for the round. |
| **Seat** | One of the four table positions: North, East, South, West. |
| **Partnership / Team** | Two players seated opposite each other: North+South, East+West. |
| **Dix** | The nine of the trump suit, worth meld points. |

### 1.4 Requirement conventions

- Requirements are identified as **FR-n** (functional), **UI-n** (user
  interface), **RT-n** (real-time/transport), **NFR-n** (non-functional), and
  **ARC-n** (architectural).
- **Shall** denotes a mandatory requirement; **should** denotes a strong
  preference; **may** denotes an option.

---

## 2. Actors

### 2.1 Player

- **FR-1** A game shall have exactly four players.
- **FR-2** Each player shall be either **human** (decisions submitted from a
  browser client) or **computer** (decisions produced by a server-side
  strategy). The two kinds shall be freely mixable, including all-human and
  all-computer games.
- **FR-2a** A seat's designation shall be fixed when the game is set up and
  shall not change for the life of the game. There is no substitution: a
  computer seat is never taken over by a person, and a human seat is never
  handed to the computer, however long that player is away.
- **FR-3** Players shall be assigned to the four seats North, East, South, and
  West. Turn order shall proceed clockwise: North → East → South → West →
  North.
- **FR-4** The four players shall form two partnerships of players seated
  opposite one another: North+South ("NS") and East+West ("EW").
- **FR-4a** Partnership membership shall be derived from the seat, never stored
  alongside it. The team identifiers `NS` and `EW` are fixed by the seating and
  are not configurable; a team's *name* is. It shall be impossible to represent
  a player seated North who belongs to East/West.
- **FR-5** Each player shall have a stable identifier and a human-readable
  display name.

### 2.2 Administrator

- **FR-6** An administrator shall create a game, which produces a unique game
  identifier.
- **FR-7** The administrator shall specify all four players: for each, the
  display name, the seat, and whether the player is human or computer.
- **FR-8** The administrator may also be one of the players.
- **FR-9** The administrator shall initiate play once four players and two
  teams are registered. The system shall reject the request to start if fewer
  or more than four players are seated, or if any seat is unfilled or
  duplicated.
- **FR-10** For each human player, game creation shall produce a join link
  containing the game identifier and an opaque, unguessable per-seat token. The
  administrator distributes these links. Opening a link shall seat the holder
  as that player.
- **FR-10a** The token shall be the sole credential for a seat. All player
  actions and the player's event stream shall be authorized by it, and the
  server shall serve a given player's hand only to the holder of that seat's
  token.
- **FR-10b** All four players shall join before play begins. A client follows
  the game entirely from the event stream, and a client that opens one late —
  a reconnection, or a second tab for the same seat — is caught up by replay
  rather than by a snapshot (see RT-5, RT-5a).
- **FR-10c** A seat token may drive several concurrent client connections. All
  of them shall show that seat's view and shall receive the same events, and
  any of them may act for the seat. Opening a seat in a second browser shall
  not disconnect the first.

---

## 3. Game flow

The system shall enforce the following phase machine. Actions submitted for a
phase other than the current one shall be rejected with an error, and the game
state shall be left unchanged.

```
SETUP → DEALER_SELECTION → [ round ]* → FINISHED

round: DEALING → BIDDING ─┬─────────────→ TRUMP → PASSING → MELDING
                          │                                    │
                          ├─ CONFIRMING ─→ TRUMP     ┌─────────┴─────────┐
                          │   (lone bidder, FR-32)   ↓                   ↓
                          │                       PLAYING            (toss in,
                          └─ ABANDONED               │                FR-50b)
                              (all pass, FR-31;      ↓                   │
                               or bid declined)   SCORING ←──────────────┘
                                    │                │
                                    └────────────────┴──→ next round
```

Two phases wait on a player rather than on the server: `CONFIRMING`, where a
lone bidder chooses whether to be held to their bid, and `MELDING`, where the
auction winner reads the table and chooses to play or concede. Neither is
timed. The only server-owned pause left is the trick clear (UI-15).

### 3.1 Dealer selection

- **FR-11** At the start of a game, a shuffled deck shall be presented
  face-down and spread out. Each of the four players shall select exactly one
  card from it.
- **FR-12** Each card may be selected by at most one player; the four drawn
  cards shall be four distinct physical cards from the same deck.
- **FR-11a** The spread shall be modelled as 48 addressable positions over one
  shuffled deck. A player draws by clicking a face-down card in the spread,
  which is then turned face up, revealing the card that lies at that position.
  A position already taken shall be rejected. This is what makes FR-12 hold by
  construction rather than by a uniqueness check.
- **FR-11b** A computer player shall draw by choosing an untaken position at
  random. Its choice shall be made through the same call a human client uses.
- **FR-11c** The spread shall be presented as a deck thrown across the table:
  the cards strewn irregularly over the inner portion of the felt rather than
  laid out in ranks, turned at differing angles, and lying across one another.
  A player shall be able to drag any card of the spread aside, to see or to
  reach what lies under it; a card so dragged stays where it is put and stays
  over what it was pulled off. Dragging a card moves it and shall not select
  it — selecting is the click of FR-11a. A card that lies under another is
  reached by moving what covers it, which is the deliberate overlap UI-18
  excepts.
- **FR-11d** A card once drawn shall leave the spread and be shown face up in
  front of its drawer's seat, where that player's hand is about to be dealt,
  for as long as the selection lasts. Which card each player drew and whose it
  is are then one thing on screen rather than two (FR-15).
- **FR-13** The player drawing the highest card shall become the dealer for the
  first round.
- **FR-14** If two or more players tie for the highest card, the entire
  selection shall be repeated — deck reshuffled, all four players draw again,
  including those who did not tie — until a single player holds the highest
  card. Suit shall never break a tie.
- **FR-15** Each player's drawn card shall be revealed to all players.
- **FR-16** After each round, the deal shall pass to the next player clockwise.
  Dealer selection shall not be repeated during a game.

### 3.2 The deck

- **FR-17** The deck shall be a standard 48-card Pinochle deck: two copies each
  of 9, Jack, Queen, King, 10, Ace, in each of the four suits.
- **FR-18** Card rank order, from lowest to highest, shall be:
  9 < Jack < Queen < King < 10 < Ace. (Note the Pinochle-specific placement of
  the 10 above the King.)
- **FR-19** The two copies of a given rank-and-suit shall be interchangeable
  for all rule purposes.

### 3.3 Dealing

- **FR-20** The deck shall be shuffled before each deal.
- **FR-21** Cards shall be dealt three at a time, in clockwise order, beginning
  with the player to the dealer's left, until the deck is exhausted. Each
  player shall receive 12 cards.
- **FR-22** A player shall see only their own hand. The other three hands shall
  never be transmitted to a client that does not own them.
- **FR-23** A player's hand shall be displayed grouped by suit in the order
  Spades, Hearts, Clubs, Diamonds, and within each suit descending by rank
  (Ace, Ten, King, Queen, Jack, Nine). The suit groups shall alternate between
  black and red. A hand is fanned (UI-4), so only each card's corner index is
  showing; two groups of the same colour side by side leave a seam that has to
  be read rather than seen.
- **FR-23a** Once trump is named, the trump suit shall move to the leftmost
  position and the other three shall follow it, the colours still alternating.
  Where either suit of the required colour would serve, the one earlier in
  FR-23's order shall come first — so the four orders are ♠♥♣♦, ♥♠♦♣, ♣♥♠♦ and
  ♦♠♥♣, each keeping as much of FR-23's order as alternation allows. This is
  the only time a hand shall be reordered during a round; the re-sort shall be
  animated or otherwise made visible so cards do not appear to teleport.

### 3.4 Bidding

- **FR-24** Bidding shall proceed clockwise, beginning with the player to the
  dealer's left.
- **FR-25** On their turn a player shall either place a bid or pass.
- **FR-26** A bid shall be an integer multiple of 10.
- **FR-27** The first (lowest legal opening) bid shall be at least 250.
- **FR-28** Each subsequent bid shall be strictly greater than the current high
  bid. Since all bids are multiples of 10, the minimum raise is 10. There shall
  be no upper limit on a bid; a player may bid any multiple of 10 above the
  current high, whether or not their hand can support it.
- **FR-29** A player who passes shall be removed from the remainder of the
  bidding for that round and shall not bid again.
- **FR-30** Bidding shall end when three players have passed. The remaining
  player wins the auction at their last stated bid, which becomes the contract.
- **FR-31** If all four players pass without any bid being placed, the round
  shall be abandoned. No score shall change, the deal shall pass to the next
  player clockwise, and a new round shall begin.
- **FR-32** If exactly one player places a bid and the other three all pass,
  that player — whoever they are, not only the player left of the dealer —
  shall be offered the option to decline the contract. If they decline, the
  round shall be abandoned exactly as in FR-31. If they accept, they win the
  auction at their bid. A player who was outbid and later inherits the auction
  because everyone else passed is not a lone bidder and gets no such option.
- **FR-33** Every bid and pass shall be visible to all four players as it is
  made, including the bidder's identity and the amount.

### 3.5 Naming trump

- **FR-34** The auction winner, and only the auction winner, shall name the
  trump suit.
- **FR-35** The named trump suit shall apply for the remainder of the round and
  shall affect both meld valuation and trick-taking.
- **FR-36** The trump suit shall be announced to all four players.

### 3.6 Passing cards

- **FR-37** The auction winner's partner shall select exactly four cards from
  their own hand and pass them to the auction winner.
- **FR-38** The passed cards shall be visible to both members of the auction
  winner's team and shall not be visible to the opposing team.
- **FR-39** The passed cards shall be added to the auction winner's hand,
  giving them 16 cards.
- **FR-40** The auction winner shall then select exactly four cards from their
  16-card hand and pass them back to the partner. These four shall likewise be
  visible only to the auction-winning team.
- **FR-41** After the exchange, both players on the auction-winning team shall
  again hold 12 cards.
- **FR-42** The exchange shall be strictly ordered: the partner passes first,
  and only once the auction winner holds those four cards may they choose the
  four to pass back. A pass submitted out of this order shall be rejected.
- **FR-43** A pass shall be rejected if it does not consist of exactly four
  cards currently held by the passing player.
- **FR-43a** Only the auction-winning team exchanges cards. The two players on
  the opposing team neither pass nor receive, and their hands are untouched
  between the deal and the first trick.

### 3.7 Meld

- **FR-44** After the pass and before the first trick, each player's meld shall
  be identified from their 12-card hand and exposed face-up on the table in
  front of them.
- **FR-45** Each player's meld total, and each team's meld total, shall be
  displayed to all players.
- **FR-46** Meld shall be scored from the hands **as they stand after the
  pass**. Meld points shall be recorded at this moment and shall not be
  recomputed later, since the cards leave the hand during trick play.
- **FR-47** The following combinations shall be recognized, with the doubled
  column applying when the player holds both copies:

  | Combination | Cards | Points | Doubled |
  | --- | --- | --- | --- |
  | Run | A-10-K-Q-J of trump | 150 | 1500 |
  | Royal marriage | K-Q of trump | 40 | — |
  | Marriage | K-Q of a non-trump suit | 20 | — |
  | Pinochle | Q♠ + J♦ | 40 | 300 |
  | Aces around | one Ace of each suit | 100 | 1000 |
  | Kings around | one King of each suit | 80 | 800 |
  | Queens around | one Queen of each suit | 60 | 600 |
  | Jacks around | one Jack of each suit | 40 | 400 |
  | Dix | 9 of trump | 10 each | — |

- **FR-48** A single card may be counted in more than one combination of
  different categories (e.g. the trump King counts toward both the run and
  Kings-around), but shall not be counted twice within the same category.
- **FR-48a** Meld shall be detected within a single player's hand and the two
  partners' totals then summed. Cards held by different players shall never
  combine: a King in one partner's hand and a Queen in the other's is not a
  marriage. A team's meld is the sum of two independent detections, never a
  detection over the twenty-four cards jointly held.
- **FR-49** A run shall consume exactly one trump King and one trump Queen.
  Any trump King-Queen pair remaining after the runs have been accounted for
  shall score a royal marriage. A hand holding a run plus a spare trump K-Q
  therefore scores 150 + 40 = 190.
- **FR-50** Meld shall be computed by the server from the player's hand. A
  player shall not declare or claim their own meld, and shall not be able to
  under-claim or over-claim it.
- **FR-50a** The MELDING phase shall hold until the auction winner acts, with
  no timer. The server exposes every player's meld, records the team totals per
  FR-46, and waits. The auction winner is the right person to hold the game
  open: they lead the first trick, so play cannot usefully begin before they
  are ready. No other player may end the display.
- **FR-50b** At that same moment the auction winner shall be offered a second
  option: to **toss the contract in** rather than play it out. This is the
  first point at which they have seen both their final twelve cards and every
  exposed meld, and so the first point at which they can judge the contract
  unmakeable.
- **FR-50c** When a contract is tossed in, the contract amount shall be
  deducted from the bidding team's cumulative score and the opposing team shall
  add their meld. Neither side scores trick points and no last-trick bonus
  arises, because no trick is played.
- **FR-50d** Tossing in shall therefore cost the bidding team **less** than
  playing on and going set, which forfeits the contract *and* their meld
  (FR-63). Conceding caps the loss, and that asymmetry is what makes the option
  worth taking on a hopeless hand rather than a formality.

### 3.8 Trick play

- **FR-51** The auction winner shall lead the first trick.
- **FR-52** Play within a trick shall proceed clockwise from the leader. Each
  player shall play exactly one card.
- **FR-53** The following play restrictions shall be enforced in order, and the
  server shall reject any card that violates them:
  1. If the player holds one or more cards of the led suit, they shall play a
     card of the led suit; and if they hold a card of the led suit that beats
     the current highest card of the led suit, they shall play such a card.
  2. Otherwise, if the player holds one or more trumps, they shall play a
     trump; and if a trump has already been played and they hold a higher
     trump, they shall play a higher trump.
  3. Otherwise, they may play any card.
- **FR-54** The trick shall be won by the highest trump played; if no trump was
  played, by the highest card of the led suit. Cards of other suits cannot win.
- **FR-55** When two identical cards are the joint highest, the one played
  first shall win the trick.
- **FR-56** The winner of a trick shall collect all four cards on behalf of
  their team and shall lead the next trick.
- **FR-57** Each played card shall become visible to all four players as soon
  as it is played.
- **FR-58** Play shall continue for twelve tricks, until all hands are empty.

### 3.9 Scoring a round

- **FR-59** Captured cards shall be worth: Ace 10, Ten 10, King 5, Queen 5,
  Jack 0, Nine 0. The 48-card deck therefore holds 240 card points.
- **FR-60** The team winning the last trick shall receive an additional 10
  points, bringing the total available from trick play to 250.
- **FR-61** Each team's round total shall be its recorded meld (FR-46) plus its
  captured card points plus any last-trick bonus.
- **FR-62** If the auction-winning team's round total is greater than or equal
  to the contract, that total shall be added to their cumulative score.
- **FR-63** If the auction-winning team's round total is less than the
  contract, they are **set**: they score nothing for the round, and the sum of
  the contract amount and their own meld for the round shall be subtracted from
  their cumulative score. A team that bids 300, melds 90, and finishes at 260
  therefore loses 390.
- **FR-64** The non-bidding team shall add their meld plus their captured card
  points to their cumulative score, **unless they took no tricks at all**, in
  which case they shall score zero for the round (meld included).
- **FR-65** Cumulative scores may go negative.
- **FR-66** After each round the system shall display, for both teams: meld,
  trick points, round total, and new cumulative score; and shall state whether
  the auction-winning team made the contract or went set.

### 3.10 Ending the game

- **FR-67** The game shall end as soon as a team's cumulative score reaches or
  exceeds **2000** points, evaluated at the end of a round. A score of exactly
  2000 wins.
- **FR-68** If exactly one team is at or above 2000, that team wins.
- **FR-69** If both teams are at or above 2000 after the same round, the
  auction-winning team of that round wins.
- **FR-70** If neither team is at or above 2000, a new round shall begin with
  the deal passing clockwise.
- **FR-71** The result shall be announced to all four players, and the game
  shall accept no further play actions.

---

## 4. Architecture

- **ARC-1** The server shall follow a ports-and-adapters (hexagonal)
  architecture. The domain and application layers shall contain no dependency
  on web frameworks, transport, storage technology, or presentation.
- **ARC-2** The server shall be the sole authority on game state and rules. The
  client shall be a rendering and input surface only; no rule shall be enforced
  solely on the client.
- **ARC-3** Each domain model shall live in its own module named after the
  class in snake_case. Each port shall likewise be a single abstract base class
  in its own module.
- **ARC-4** Ports shall be defined with `abc.ABC` and `@abstractmethod`.
- **ARC-5** The system shall expose driving ports for administrative use cases
  and for player actions, and driven ports for state persistence, player
  notification, and card image resolution.
- **ARC-6** Game state persistence shall be behind a port so that the in-memory
  implementation used for development and tests can be replaced without
  changing domain or application code.
- **ARC-7** The server shall be built on **FastAPI**. Player actions and
  administrative commands shall be submitted as ordinary HTTP requests; state
  changes shall be pushed to clients over **Server-Sent Events**, one stream
  per seated player. The SSE endpoint is a driving adapter over the
  notification port and shall contain no game logic.
- **ARC-8** The browser client shall be written in **TypeScript with no UI
  framework**, compiled with `tsc` and served as static assets. No bundler or
  runtime dependency shall be required to run it.
- **ARC-9** Deferred execution shall be reached through a driven port — a
  scheduler that accepts "invoke this after *n* seconds". The domain and
  application layers shall express delays through that port and shall not
  import `asyncio`, `time.sleep`, or any other concrete timing mechanism, in
  keeping with ARC-1. The production adapter is asyncio-based; tests shall use
  a fake that advances a virtual clock on demand.
- **ARC-10** No automated test shall wait in real time for a game pause. A test
  that exercises a timed transition shall advance the fake scheduler instead.

---

## 5. User interface

- **UI-1** Each player's browser shall render the table from that player's own
  seat, drawn at the bottom of the screen. The other three players shall appear
  to the left, across, and to the right, matching their true clockwise
  relationship.
- **UI-2** The table background shall be a green felt surface, resembling a
  physical card table.
- **UI-3** Each player's name shall be displayed at their seat. The
  partnerships shall be visually distinguishable.
- **UI-4** The viewing player's own hand shall be shown face-up, fanned, and
  ordered per FR-23.
- **UI-5** The other three hands shall be shown as fanned card backs, with the
  correct number of cards remaining.
- **UI-6** The centre of the table shall be the trick area. Each played card
  shall be positioned nearer the player who played it, so that all four cards
  of the trick are simultaneously visible and attributable.
- **UI-7** The player whose turn it is shall be clearly indicated to everyone.
- **UI-8** A human player shall play a card either by dragging it from their
  hand to the centre of the table, or by clicking it. Dragging is the primary
  affordance; clicking a legal card shall be exactly equivalent. The same pair
  of gestures shall apply wherever cards are selected, including the pass.
- **UI-9** The client shall visually distinguish cards that are legal to play
  from those that are not, and shall refuse to submit an illegal play.
- **UI-10** The bidding interface shall let a player enter a bid (constrained
  to multiples of 10 at or above the current minimum) or pass, and shall show
  the running bid history.
- **UI-11** The trump-naming interface shall let the auction winner choose one
  of the four suits.
- **UI-12** The passing interface shall let a player select exactly four cards
  and confirm, and shall show the received cards to the receiving team only.
- **UI-13** Exposed meld shall be displayed face-up in front of each player,
  with per-player and per-team totals.
- **UI-14** A persistent scoreboard shall show both teams' cumulative scores,
  the current contract, the auction winner, and the trump suit.
- **UI-14a** The scoreboard shall additionally retain, for the whole round, the
  bid history and each team's meld total — the latter remaining visible after
  the exposed meld has been cleared from the table. These were public
  information when they occurred, so keeping them on screen restores what a
  player at a physical table would have seen and remembered.
- **UI-14b** The last completed trick shall be viewable on demand for the
  duration of the following trick, mirroring the courtesy of asking to see the
  last trick before it is turned. Tricks before that one shall not be
  reviewable.
- **UI-14c** The interface shall **not** display a running total of card points
  taken during a round. Counting the cards as they fall is a genuine part of
  playing well, and a live total would remove it. Trick points shall appear
  only in the round summary of FR-66, after play is over.
- **UI-15** A completed trick shall remain visible for a fixed, configurable
  interval — approximately 1.5 seconds by default — and shall then be cleared
  automatically to the winner. Clearing shall not require any player action.
  The interval shall be counted by the server, which publishes an event when
  the trick is cleared; the client shall not run this timer itself (RT-8).
- **UI-16** Card artwork shall be served for both faces and backs. The system
  shall support at least one raster or vector format for each card.
- **UI-17** The interface shall be usable on current desktop versions of Chrome
  and Firefox, at a typical desktop window size. The table may be a fixed
  layout scaled to the viewport rather than a responsive one. Tablet and phone
  support are not requirements, but the design should not gratuitously preclude
  them.
- **UI-18** Every control the interface presents as available shall receive the
  clicks aimed at it. A control that is drawn and enabled shall be reachable
  where it is drawn, with nothing positioned over it that takes the click
  instead; the same shall hold for the regions a card may be dragged onto
  (UI-8), which shall accept a drop wherever they are shown as a target. This
  shall hold throughout a round and at every window size the layout supports
  (UI-17). An unreachable control is worse than an absent or a disabled one:
  the interface goes on offering the action, and refusing it silently, so the
  player is given no account of why nothing happened. The scattered spread of
  FR-11c is the one exception, and is one because the overlap is the point: its
  cards lie across one another, any one of them will do, and the player's
  remedy is to move what is in the way. What must hold there is that cards
  enough to draw from are reachable, not that every card is.
- **UI-19** The interface shall present a notice area that states the outcome
  of each stage of play as that stage concludes: who won the draw for the deal,
  who won the auction and at what, which suit is trump, who took the trick, and
  how the round scored. One notice shall be shown at a time, each replacing the
  one before it. A notice is public: all four seats shall see the same words,
  and shall see them at the same moment (RT-11).
  The wording shall be composed by the client from the events it has already
  received, and shall not be sent as text by the server. Every fact a notice
  states is already published as an event, and the event is the authoritative
  copy of it; a second copy in prose could disagree with the first.
  There shall be no scrolling history of notices. What deserves to outlive its
  moment is named by UI-14a and belongs on the scoreboard; the rest passes, as
  it does at a physical table.
- **UI-19a** A notice shown while the game is holding for a player (RT-13)
  shall present the control that releases the hold, and shall present it within
  the notice itself, so that what must be read and what ends the reading are
  the same object on screen. Any seated player may use it. A notice shown
  during a timed hold shall offer no such control: nothing a player does
  shortens it.
  The notice area is not the turn indicator of UI-7, which says whose turn it
  is rather than what has just happened; nor the report of a refused action
  (NFR-4), which concerns one player's own attempt and is shown only to them;
  nor the stream-status indicator of RT-5b, which is a fact about a browser
  rather than about the game.

---

## 6. Real-time behaviour

- **RT-1** Each client shall see only the information its player is entitled
  to: their own hand, public events, and team-private information (the pass)
  where applicable. Private state shall be filtered on the server, not hidden
  on the client.
- **RT-2** State changes shall be delivered to clients by server push. Clients
  shall not poll for state.
- **RT-3** The display shall update as soon as a play is made, without
  requiring user action.
- **RT-4** The following events shall be published: dealer selected, cards
  dealt (per player, privately), bid placed, trump named, cards passed (to the
  passing team only), meld exposed, card played, trick completed, round scored,
  game over.
- **RT-5** A client builds its view from the event stream alone. The server
  shall not construct a point-in-time snapshot of a game in progress; there is
  one authoritative history, and it is the sequence of events.
- **RT-5a** A client that loses its stream shall be able to resume it. Every
  frame carries a sequence number; on reconnecting, a client shall present the
  last one it received, and the server shall replay the frames that seat
  missed — its own private frames and the table's broadcasts, never another
  seat's — before resuming live delivery. Replay is bounded: where the server
  can no longer reach back far enough, it shall say so rather than deliver a
  history with a hole in it.
- **RT-5b** A client shall show whether its stream is live, and shall not
  submit actions while it is not. A table that has stopped being told what
  happens is frozen, not merely quiet, and shall not be presented as playable.
- **RT-6** Computer players' actions shall be produced by the server and
  published through the same event stream as human actions, so that clients
  need not distinguish between them.
- **RT-7** A computer player's move should be delayed slightly so that human
  players can follow the play. See FR-75c.
- **RT-8** Every timed pause in the game — the trick-clear interval (UI-15),
  and the computer-move delay (FR-75c) — shall be
  owned and counted by the server. The client shall hold no timers that affect
  what it displays: it renders the state it was last told about and changes
  only when an event tells it to.
- **RT-9** A timed pause is therefore a real state the game occupies, not a
  presentation effect. While the game is paused, player actions that would
  advance past the pause shall be rejected exactly as any other out-of-phase
  action (NFR-4); the next leader shall not be able to play before the
  completed trick has been cleared.
- **RT-10** A timed pause shall be delimited by events — one marking its start
  and one its end — rather than inferred by the client from a clock. This keeps
  the client's rule simple: render what the last event said.
- **RT-11** Because all four clients are driven from one clock, they shall
  display the same phase at the same time, to within network latency. No client
  shall be able to run ahead of or behind the others.
- **RT-12** Nothing acts for a seat whose player is absent (FR-2a), so play
  blocks there until they return. A seat that reconnects within the replay
  window resumes and play continues (RT-5a); one that does not leaves the game
  unable to be completed. The remaining players shall be told when a seat is
  lost and when it comes back, so they can wait or abandon the game
  deliberately rather than sit in front of a table that has simply stopped.
- **RT-13** A pause shall be modelled as a *hold*: a named state the game
  occupies, counted by the server (RT-8) and delimited by published events
  (RT-10). A hold shall end in one of exactly two ways, fixed at the moment it
  begins — after a stated interval, or when a player releases it. The
  trick-clear interval of UI-15 is a hold of the first kind.
  A hold that waits on a player shall be released by any one seated player. It
  shall not require all four, and it shall not require the administrator: the
  players at a table are in contact with one another outside the game, and a
  table that cannot go on until four people have each clicked is slower than
  the conversation it exists to keep pace with. Requiring the administrator
  would make a game depend on someone who need not be watching it at all.
  Releasing a hold shall be idempotent and shall name the hold it releases. A
  release naming a hold that has already ended shall succeed and change
  nothing, rather than being reported to the player as a failure — two players
  may well click at the same moment, and neither of them has done anything
  wrong.
  A hold that waits on a player shall wait indefinitely; it shall not also be
  given an interval after which it ends by itself. Such an interval would undo
  the control it was attached to, resuming the game while the players are still
  talking about what the notice says. A table at which nobody remains to
  release a hold is the case RT-12 already describes, and the administrator
  ending the game is already its remedy.
  It follows that a hold which waits on a player shall be taken only at a table
  that has one. Where every seat is a computer (FR-72) there is nobody to read
  what the hold is showing and nobody who could ever end the wait, so such a
  table shall proceed as though the hold had been released at once. The test is
  the seat's kind, not whether its player is presently connected: a human seat
  that has gone quiet is RT-12's case, where play blocks until they return, and
  that is the wanted behaviour here too.

---

## 7. Computer player

- **FR-72** A computer player shall be able to perform every action a human can:
  draw for the deal, bid or pass, name trump, select cards to pass, and play a
  card.
- **FR-73** A computer player shall never make an illegal move.
- **FR-74** A computer player shall base its decisions only on information its
  seat is entitled to. It shall not read other players' hands, and shall be
  driven through the same ports a human client uses.
- **FR-75** The decision logic shall be replaceable, so that strategies of
  different strength can be swapped in. The system shall ship exactly one
  strategy; selectable difficulty levels are out of scope for this release.
- **FR-75a** The computer player shall bid on the basis of what its
  *partnership* can score, since a contract is scored against both partners'
  meld and the card points the partnership takes. Its valuation shall be its
  own detected meld in the prospective trump suit, plus a conservative estimate
  of the trick points **both hands together** can take, derived from its aces
  and its length in that suit, plus an allowance for what its partner can be
  assumed to contribute. It shall pass rather than bid beyond that valuation.
  The allowance shall be a single figure that can be tuned by playing games,
  not a model of the partner's hand: a computer player never sees its partner's
  cards (FR-74). A valuation confined to its own twelve cards would be unable
  to reach the FR-27 minimum of 250 and the player would pass unconditionally.
- **FR-75b** When passing to a partner who won the auction, the computer player
  shall pass cards that support the contract — trump and aces — while retaining
  cards that complete its own meld. It shall not simply pass its lowest cards.
- **FR-75c** A computer player's action shall be delayed by a configurable
  interval, defaulting to approximately one second, so that human players can
  follow the play. The delay shall be reducible to zero so that all-computer
  games can be run at full speed in testing.

---

## 8. Non-functional requirements

- **NFR-1** The server shall target Python 3.12 or later.
- **NFR-2** All optional and development dependencies shall be declared in
  `[project.dependencies]` in `pyproject.toml`, so that `pip install -e .` is
  sufficient to run the tests.
- **NFR-3** Unit tests shall use pytest. Domain rules — bidding validity, meld
  detection, trick resolution, and round scoring — shall be covered by tests
  that do not require a running server or browser.
- **NFR-4** An action submitted by the wrong player, at the wrong time, or with
  invalid arguments shall be rejected with a clear error, and the game state
  shall be left exactly as it was.
- **NFR-5** The system shall support one game in progress at a time. Running a
  second game concurrently is not a requirement, and the transport, seat
  tokens, and administrative surface need not accommodate it. The existing
  game-id keying of the state port shall nevertheless be retained, since it
  costs nothing and leaves the option open.
- **NFR-6** The server shall not transmit a player's hand to any other player's
  client under any circumstances.
- **NFR-7** Randomness used for shuffling shall be seedable in tests so that
  deals can be reproduced.
- **NFR-8** Game state shall be held in memory only, behind `GameStatePort`. A
  server restart may lose a game in progress; no durable storage is required
  for this release.
- **NFR-9** The server shall log every accepted player action and every
  published event, tagged with the game id, at a level that can be enabled
  without a code change. Rejected actions shall be logged with the reason.
  Hands and deals shall not be logged, so that the log is not itself a leak of
  private state.
