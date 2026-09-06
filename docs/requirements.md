# Pinochle — Requirements

**Status:** Draft
**Last updated:** 2026-09-06
**Source:** Expanded from `prompt.md`

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
- Open questions are identified as **OQ-n** and collected in §10. Requirements
  that depend on an unresolved question are annotated `[see OQ-n]`.

---

## 2. Actors

### 2.1 Player

- **FR-1** A game shall have exactly four players.
- **FR-2** Each player shall be either **human** (decisions submitted from a
  browser client) or **computer** (decisions produced by a server-side
  strategy). The two kinds shall be freely mixable, including all-human and
  all-computer games.
- **FR-3** Players shall be assigned to the four seats North, East, South, and
  West. Turn order shall proceed clockwise: North → East → South → West →
  North.
- **FR-4** The four players shall form two partnerships of players seated
  opposite one another: North+South ("NS") and East+West ("EW").
- **FR-4a** Partnership membership shall be derived from the seat, never stored
  alongside it. The team identifiers `NS` and `EW` are fixed by the seating and
  are not configurable; a team's *name* is. It shall be impossible to represent
  a player seated North who belongs to East/West. `[OQ-32, resolved]`
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
  as that player. `[OQ-1, resolved]`
- **FR-10a** The token shall be the sole credential for a seat. All player
  actions and the player's event stream shall be authorized by it, and the
  server shall serve a given player's hand only to the holder of that seat's
  token.
- **FR-10b** A join link shall remain usable for the life of the game, so that
  a player who closes their browser can return to their seat (see FR-76).
- **FR-10c** A seat token may drive several concurrent client connections. All
  of them shall show that seat's view and shall receive the same events, and
  any of them may act for the seat. Opening a seat in a second browser shall
  not disconnect the first. `[OQ-1, resolved]`

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
  shuffled deck. A player draws by naming a position, and receives the card
  that lies there. A position already taken shall be rejected. This is what
  makes FR-12 hold by construction rather than by a uniqueness check.
  `[OQ-31, resolved]`
- **FR-11b** A computer player shall draw by choosing an untaken position at
  random. Its choice shall be made through the same call a human client uses.
- **FR-13** The player drawing the highest card shall become the dealer for the
  first round.
- **FR-14** If two or more players tie for the highest card, the entire
  selection shall be repeated — deck reshuffled, all four players draw again,
  including those who did not tie — until a single player holds the highest
  card. Suit shall never break a tie. `[OQ-2, resolved]`
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
  Spades, Hearts, Diamonds, Clubs, and within each suit descending by rank
  (Ace, Ten, King, Queen, Jack, Nine). `[OQ-3, resolved]`
- **FR-23a** Once trump is named, the trump suit shall move to the leftmost
  position, the remaining three suits keeping their relative order. This is the
  only time a hand shall be reordered during a round; the re-sort shall be
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
  current high, whether or not their hand can support it. `[OQ-4, resolved]`
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
  `[OQ-5, resolved]`
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
  `[OQ-6, resolved]`
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
  column applying when the player holds both copies `[OQ-7, resolved]`:

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
  therefore scores 150 + 40 = 190. `[OQ-8, resolved]`
- **FR-50** Meld shall be computed by the server from the player's hand. A
  player shall not declare or claim their own meld, and shall not be able to
  under-claim or over-claim it. `[OQ-9, resolved]`
- **FR-50a** The MELDING phase shall hold until the auction winner acts, with
  no timer. The server exposes every player's meld, records the team totals per
  FR-46, and waits. The auction winner is the right person to hold the game
  open: they lead the first trick, so play cannot usefully begin before they
  are ready. No other player may end the display.
  `[OQ-27, revised 2026-09-06]`
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
  `[OQ-10, resolved]`
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
  `[OQ-11, resolved]`
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
  therefore loses 390. `[OQ-12, resolved]`
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
  2000 wins. `[OQ-13, resolved]`
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
  changing domain or application code. `[OQ-14, resolved — in-memory only]`
- **ARC-7** The server shall be built on **FastAPI**. Player actions and
  administrative commands shall be submitted as ordinary HTTP requests; state
  changes shall be pushed to clients over **Server-Sent Events**, one stream
  per seated player. The SSE endpoint is a driving adapter over the
  notification port and shall contain no game logic. `[OQ-23, resolved]`
- **ARC-8** The browser client shall be written in **TypeScript with no UI
  framework**, compiled with `tsc` and served as static assets. No bundler or
  runtime dependency shall be required to run it. `[OQ-24, resolved]`
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
  `[OQ-15, resolved]`
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
  player at a physical table would have seen and remembered. `[OQ-29, resolved]`
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
  `[OQ-16, resolved]`
- **UI-16** Card artwork shall be served for both faces and backs. The system
  shall support at least one raster or vector format for each card.
- **UI-17** The interface shall be usable on current desktop versions of Chrome
  and Firefox, at a typical desktop window size. The table may be a fixed
  layout scaled to the viewport rather than a responsive one. Tablet and phone
  support are not requirements, but the design should not gratuitously preclude
  them. `[OQ-17, resolved]`

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
- **RT-5** A client that loses its connection and reconnects, using its
  original join link, shall receive a full snapshot of the current game state
  from its own seat's point of view, sufficient to render the table without
  replaying earlier events. Play resumes where it stopped. `[OQ-18, resolved]`
- **RT-6** Computer players' actions shall be produced by the server and
  published through the same event stream as human actions, so that clients
  need not distinguish between them.
- **RT-7** A computer player's move should be delayed slightly so that human
  players can follow the play. See FR-75c. `[OQ-19, resolved]`
- **RT-8** Every timed pause in the game — the trick-clear interval (UI-15),
  and the computer-move delay (FR-75c) — shall be
  owned and counted by the server. The client shall hold no timers that affect
  what it displays: it renders the state it was last told about and changes
  only when an event tells it to. `[OQ-30, resolved]`
- **RT-9** A timed pause is therefore a real state the game occupies, not a
  presentation effect. While the game is paused, player actions that would
  advance past the pause shall be rejected exactly as any other out-of-phase
  action (NFR-4); the next leader shall not be able to play before the
  completed trick has been cleared.
- **RT-10** The snapshot sent to a reconnecting client (RT-5) shall convey any
  pause in progress, including what is being displayed during it — the
  completed trick, or the exposed meld — so that a client reconnecting mid-pause
  does not render the state that follows it.
- **RT-11** Because all four clients are driven from one clock, they shall
  display the same phase at the same time, to within network latency. No client
  shall be able to run ahead of or behind the others.

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
  different strength can be substituted. The system shall ship exactly one
  strategy; selectable difficulty levels are out of scope for this release.
  `[OQ-21, resolved]`
- **FR-75a** The computer player shall bid on the basis of its detected meld
  plus a conservative estimate of the trick points its hand can take, derived
  from its aces and its length in the prospective trump suit. It shall pass
  rather than bid beyond that estimate. `[OQ-20, resolved]`
- **FR-75b** When passing to a partner who won the auction, the computer player
  shall pass cards that support the contract — trump and aces — while retaining
  cards that complete its own meld. It shall not simply pass its lowest cards.
- **FR-75c** A computer player's action shall be delayed by a configurable
  interval, defaulting to approximately one second, so that human players can
  follow the play. The delay shall be reducible to zero so that all-computer
  games can be run at full speed in testing. `[OQ-19, resolved]`
- **FR-76** When a human player is disconnected, play shall block at that seat
  and the other players shall be told the seat is waiting. The game shall not
  be abandoned and no timeout shall act on its own. `[OQ-18, resolved]`
- **FR-77** The administrator shall be able to convert a disconnected human
  seat to a computer player, at which point play resumes immediately with the
  strategy acting for that seat. The substitution shall be announced to all
  players.
- **FR-78** A substitution shall be reversible. A human presenting the seat's
  original join link shall reclaim the seat, and the computer strategy shall
  stop acting for it. `[OQ-26, resolved]`
- **FR-79** A reclaim shall take effect at the next decision point for that
  seat. If the strategy is already committed to the current decision, that
  action shall stand and the human shall take over from the following one. A
  reclaim shall never roll back an action that has been published.
- **FR-80** Substitutions and reclaims shall both be announced to all players,
  so that everyone knows whether a seat is being played by its human.

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
  costs nothing and leaves the option open. `[OQ-22, resolved]`
- **NFR-8** Game state shall be held in memory only, behind `GameStatePort`. A
  server restart may lose a game in progress; no durable storage is required
  for this release. `[OQ-14, resolved]`
- **NFR-9** The server shall log every accepted player action and every
  published event, tagged with the game id, at a level that can be enabled
  without a code change. Rejected actions shall be logged with the reason.
  Hands and deals shall not be logged, so that the log is not itself a leak of
  private state. `[OQ-25, resolved]`
- **NFR-6** The server shall not transmit a player's hand to any other player's
  client under any circumstances.
- **NFR-7** Randomness used for shuffling shall be seedable in tests so that
  deals can be reproduced.

---

## 9. Current implementation status

This section records the gap between this document and the code as of
2026-09-06. It is informational and will go stale; it is included to make the
first round of prioritization concrete.

**Implemented:** the domain model (card, rank, suit, deck, hand, trick, meld,
bid, scoring, team, player, game aggregate), the round state machine, the
application service implementing the admin and player-action ports, the port
definitions, in-memory state and stdout-notification adapters, and a
rule-based computer strategy.

**Not yet implemented:**

1. No HTTP server, no API, and no transport of any kind. Nothing satisfies §6
   or ARC-7.
2. No browser client. Nothing satisfies §5 or ARC-8.
3. No card image assets — the `card_images` packages contain no files.
4. No runnable entry point; `create_default_app()` wires objects but nothing
   drives them.
5. No orchestration for computer players — nothing invokes the strategy.
6. No seat tokens or join links (FR-10, FR-10a, FR-10c).
7. No state snapshot for reconnecting clients (RT-5), and no per-seat view
   filtering to build one from.
8. No computer substitution or reclaim for a disconnected seat (FR-77, FR-78).
9. `SchedulerPort` (ARC-9) exists with an `ImmediateScheduler` that collapses
   every delay to zero, and the trick clear (UI-15) is wired to it. Still
   missing: the asyncio adapter that honours a real delay, the fake with a
   virtual clock (ARC-10), and the computer-move delay (FR-75c). The meld
   display is no longer a timed pause at all (FR-50a).
10. No action/event logging (NFR-9).
11. No seedable shuffle for reproducible deals in tests (NFR-7) — `Deck.shuffle`
    calls the module-level `random.shuffle`.

**Known defects against this specification**, roughly in order of severity:

- ✅ **D-1 — fixed.** Meld was computed in `_score_round` from hands that were
  empty by then, so every meld scored zero. `Round` now captures each player's
  meld at the PASSING → MELDING transition and scoring reads the recorded
  totals (FR-46, FR-48a).
- ✅ **D-2 — fixed.** `Round.advance_to_playing()` was never called, so trick
  play was unreachable. The meld hold now ends on a server-owned timer reached
  through `SchedulerPort` (ARC-9, FR-50a).
- ✅ **D-3 — fixed.** `GameService._dispatch` broadcast every event to every
  player, including `CardsDealt`. It now routes each event by a visibility
  rule: a dealt hand goes to its owner, a pass to the two partners, everything
  else is public (FR-22, RT-1, NFR-6).
- ✅ **D-4 and D-15 — fixed.** `draw_for_deal` built a fresh shuffled deck per
  call and took its top card, so two players could draw the identical card and
  the face-down spread of FR-11 did not exist. Drawing now names a position
  into one shared 48-card spread, making FR-12 hold by construction; a tie lays
  out a wholly fresh spread (FR-14); and the docstring claiming suit breaks
  ties is corrected.
- ✅ **D-5 and D-9 — fixed.** All four passing left `bid_winner` as `None` with
  a contract of 0 and advanced to `TRUMP` regardless, and a lone bidder had no
  way to decline. `RoundPhase` gained `CONFIRMING` and `ABANDONED`;
  abandonment rotates the deal and redeals with both scores untouched (FR-31,
  FR-32). Fixing this exposed a further bug: bidding ended as soon as one
  active bidder remained, so after three passes the fourth player was never
  offered a turn and could neither open nor throw the round in.
- ✅ **D-6 — fixed.** `Hand.legal_plays` enforced follow-suit and must-trump
  but not the obligation to beat, because its signature carried only the lead
  suit. It now takes the trick, and applies FR-53 in full: beat the best card
  of the led suit when following, overtrump when void and able. `Round` exposes
  `legal_plays(player_id)` for UI-9, and `play_card` now rejects an illegal
  card rather than accepting it (FR-53, NFR-4).
- ✅ **D-7 — fixed.** A run consumed every trump King-Queen pair, so a run plus
  a spare pair scored 150 rather than 190. Each run now consumes exactly one
  pair and the remainder meld as royal marriages (FR-49).
- ✅ **D-8 — fixed.** `pass_cards` accepted the two passes in either order. It
  now routes through `current_player`, so the partner passes first and the
  auction winner chooses their return while holding sixteen cards (FR-42).

- ✅ **D-10 — fixed.** `_score_round` set `GamePhase.DEALER_SELECTION` purely so
  that `set_dealer` would accept the rotation, misrepresenting a once-per-game
  phase as recurring. `Game.rotate_dealer` now expresses it directly (FR-16).
- **D-11** `Player.type` is a fixed field, but under FR-78 a seat's control can
  change between human and computer mid-game. Seat control needs to be mutable
  state that the computer-move scheduler re-checks at the moment it acts.
  *Not fixable in isolation:* substitution and reclaim (FR-77, FR-78) depend on
  seat tokens and an administrative surface, neither of which exists yet, so
  this resolves as part of the transport work rather than on its own.
- **D-12** `ComputerPlayerStrategy.choose_trump` and `choose_cards_to_pass` are
  superseded by FR-75a and FR-75b. `choose_play` is retained as-is by the
  deliberate deferral in OQ-28.
  *Not a defect so much as unbuilt work:* the current strategy is legal and
  finishes games, but it bids nothing and passes its four lowest cards, so a
  mixed human/computer game is not yet worth playing. This is the largest
  remaining piece of engine work.
- ✅ **D-13 — fixed.** `play_card` moved straight from a completed trick to the
  next, so the four cards never sat on the table. A completed trick is now held
  until `clear_trick` sweeps it; during the hold nobody is on the clock and a
  premature lead is refused (RT-8, RT-9). Still outstanding: RT-10 requires the
  hold to appear in a reconnect snapshot, which has no implementation yet.
- ✅ **D-14 — fixed.** `Player.team_id` was settable independently of the seat,
  making a North player on East/West constructible. Partnership is now derived
  from `Position`, the ids are constants in `team.py`, and `assign_teams`
  rejects renamed ids (FR-4a).

- ✅ **D-16 — fixed.** `Round.current_player` now reports who is on the clock
  for bidding, trump, passing, and trick play, and returns `None` for the
  server-driven phases. `BiddingRound` gained the turn pointer this needed and
  now enforces turn order, which its docstring had always claimed but never
  did. `Round.play_card` rejects an out-of-turn play in every seat, not only
  the lead (UI-7, RT-10, NFR-4).

---

## 10. Open issues and questions

Each item states the ambiguity, the options, and the decision or a recommended
default. Resolved items are kept in place, marked ✅ with the date, so that this
section doubles as a decision record.

**All thirty-two were settled on 2026-09-06.** OQ-28 is a deliberate deferral
rather than a decision. Nothing in this section blocks the work in §9.

### Rules

**OQ-1 — How do human players reach their seat?** ✅ **Resolved 2026-09-06:
per-seat join links.** Game creation mints an opaque token per human seat; the
administrator distributes the links. See FR-10, FR-10a, FR-10b.
A token may drive several concurrent connections; they all share the seat and
any of them may act for it. See FR-10c.

**OQ-2 — On a dealer-selection tie, do all four players redraw, or only those
tied?** ✅ **Resolved 2026-09-06: all four redraw.** The deck is reshuffled and
the whole selection repeats, matching `prompt.md`. Suit never breaks a tie. See
FR-14.
*Consequence:* the `PlayerActionPort.draw_for_deal` docstring, which claims
ties are broken by suit, is wrong and must be corrected (D-4).

**OQ-3 — What is the hand sort order exactly?** ✅ **Resolved 2026-09-06: fixed
S-H-D-C order, rank descending, with trump moved to the left once named.** See
FR-23 and FR-23a. Note this makes the trump re-sort the only mid-round
reordering, so it needs a visible transition rather than an instant jump.

**OQ-4 — Must each bid exceed the previous by at least 10, and is there a
maximum?** ✅ **Resolved 2026-09-06: strictly greater, no ceiling.** The
multiple-of-10 rule already forces a minimum raise of 10. A player may bid
arbitrarily high, including beyond what their hand can make — bluffing and
misjudgement are part of the game, and the set penalty is the corrective. See
FR-28. This **overrides `prompt.md`**, which says each bid must be `>=` the
previous; that reading permits an endless exchange of equal bids.

**OQ-5 — What exactly happens when the first bidder is left alone?** ✅
**Resolved 2026-09-06: the option goes to whoever placed the only bid**, not
only to the player left of the dealer. See FR-32. There is no forced-bid rule;
all four players may pass, in which case FR-31 applies.
The phase machine in §3 has been extended with a `CONFIRMING` state between
BIDDING and TRUMP, entered only in the lone-bidder case, and an `ABANDONED`
outcome shared with FR-31.

**OQ-6 — Is the passing order fixed?** ✅ **Resolved 2026-09-06: strict order.**
The partner passes first; the auction winner then holds 16 cards and chooses
four to return. See FR-42.
*Consequence:* `Round.pass_cards` currently accepts the two passes in either
order and resolves when both arrive. It must be reworked to reject the auction
winner's pass until the partner's has landed, and to hold the winner at 16
cards in between.

**OQ-7 — Is the meld table correct and complete for this house's rules?** ✅
**Resolved 2026-09-06: the FR-47 table stands as written**, with big-double
values (run 1500, aces 1000, kings 800, queens 600, jacks 400, pinochle 300)
rather than merely scoring each combination twice. A dix melds 10 for *each*
nine of trump held, so both nines score 20.
*Consequence:* the existing `detect_meld` values are all correct; only the
run/marriage interaction (D-7) needs fixing.

**OQ-8 — How do runs and royal marriages interact?** ✅ **Resolved 2026-09-06:
a run plus a spare trump K-Q scores 190.** The run consumes one King and one
Queen; leftover pairs meld as royal marriages. See FR-49.
*Consequence:* `detect_meld` must count K-Q pairs remaining *after* the run
allocation rather than suppressing the trump marriage whenever a run is
present. Worth confirming the double-run case at the same time: A-10-K-Q-J
twice over is 1500 by FR-47, and consumes both K-Q pairs, so no marriage is
left over.

**OQ-9 — Is meld automatic or declared?** ✅ **Resolved 2026-09-06: automatic.**
The server detects and exposes all meld; players cannot miss or overclaim. See
FR-50 and FR-50a. The MELDING phase carries no *claiming* action; ending the
display is the auction winner's call (OQ-27).

**OQ-10 — Confirm the must-beat rules.** ✅ **Resolved 2026-09-06: overtrump is
mandatory.** A player void in the led suit must play a trump, and if a trump
has already been played and they hold a higher one, they must play a higher
one. A player void in both the led suit and trump may discard anything. FR-53
stands as written.
*Consequence:* `Hand.legal_plays` must take the current trick as an argument,
not just the lead suit — it cannot determine the current high card otherwise.

**OQ-11 — Confirm the card point values.** ✅ **Resolved 2026-09-06:
10/10/5/5/0/0.** Ace and Ten are worth 10, King and Queen 5, Jack and Nine
nothing — 240 in the deck plus the 10-point last trick. The older
11/10/4/3/2/0 scale was rejected. See FR-59; the code already matches.

**OQ-12 — What is the going-set penalty?** ✅ **Resolved 2026-09-06: contract
plus meld.** A set team loses the contract amount *and* their own meld for the
round, on the reasoning that the meld counted toward an attempt that failed.
FR-63 has been updated. Note that this **overrides `prompt.md`**, which says
only the bid is subtracted; the existing `resolve_round` implementation is
correct as written and item 13 of §9 is withdrawn.

**OQ-13 — Is the win threshold "reaches 2000" or "exceeds 2000"?** ✅
**Resolved 2026-09-06: `>= 2000`.** Exactly 2000 wins. This **overrides
`prompt.md`**, which says "exceeded"; the code is already correct. See FR-67.

**OQ-13a — Can a set hand end the game?** The threshold is evaluated after all
of a round's scoring is applied, with no special case: a team that goes set can
still be overtaken by opponents crossing 2000 in the same round, and FR-69
settles the case where both cross at once. Follows from FR-67; noted here only
because the interaction is easy to miss when writing scoring tests.

### Product and platform

**OQ-14 — Does game state need to survive a server restart?** ✅ **Resolved
2026-09-06: in-memory only.** A restart may lose a game in progress. See NFR-8.
The `GameStatePort` boundary is retained so durable storage can be added later
without touching the domain — note that doing so would require making the
`Game` aggregate serializable, which it is not today, since it holds live
`Round` and `Trick` objects.

**OQ-15 — Is drag-and-drop the only way to play a card?** ✅ **Resolved
2026-09-06: both drag and click.** Drag is primary, click is an exact
equivalent, and the pair applies to card selection everywhere. See UI-8.

**OQ-16 — How long does a completed trick stay visible, and who clears it?** ✅
**Resolved 2026-09-06: fixed delay, auto-clear**, about 1.5 seconds,
configurable, with no player acknowledgement. See UI-15. Note this also sets
the trick-clear hold only. The meld display is not a timed pause at all —
see OQ-27.

**OQ-17 — What browsers and screen sizes must be supported?** ✅ **Resolved
2026-09-06: current desktop Chrome and Firefox.** A fixed table layout scaled
to the viewport is acceptable; tablet and phone are not requirements but should
not be gratuitously precluded. See UI-17.

**OQ-18 — What is the reconnection and disconnection policy?** ✅ **Resolved
2026-09-06: the game waits, and the administrator may substitute.** No timeout
acts on its own; a disconnected seat blocks play until the player returns or
the administrator hands the seat to a computer player. Reconnecting with the
original join link yields a full state snapshot. See FR-76, FR-77, RT-5.

**OQ-26 — Is a computer substitution reversible?** ✅ **Resolved 2026-09-06:
yes, the human reclaims the seat.** Presenting the original join link takes the
seat back; the reclaim lands at the next decision point, and any action the
strategy has already published stands. See FR-78, FR-79, FR-80.
*Consequence:* whether a seat is human- or computer-controlled becomes mutable
mid-game, so it cannot stay a fixed `PlayerType` on the `Player` dataclass. The
scheduler must also check, at the moment it is due to act, that the seat is
still computer-controlled.

**OQ-27 — How does the meld display advance?** ✅ **Revised 2026-09-06: the
auction winner ends it.** Originally resolved as a long fixed timer; the user
replaced that with an explicit ready from the auction winner, and added a
second choice at the same moment — play the contract, or toss it in (FR-50a
through FR-50d).

The revision is better than what it replaced. A timer either rushes a player
who is still counting or bores three who are not, and no single interval suits
both. Handing the decision to the auction winner also puts the toss-in exactly
where it belongs: the concession needs the same information as the decision to
play, and there is no earlier point at which the winner knows both their final
hand and every opponent's meld.

**OQ-28 — When is the computer's card play improved?** ✅ **Deferred
2026-09-06.** `choose_play` keeps "always play the highest legal card" for now.
It is legal and it completes games, which is enough to exercise the full stack
end to end; the bidding and passing improvements of FR-75a and FR-75b are the
ones that matter for the game being playable at all. Revisit once the server
and client work, at which point the targets are: don't overtake a partner who
is already winning the trick, lead trump to draw it, and throw point cards to a
partner who is winning.

**OQ-30 — Who owns the game's timers, the server or the client?** ✅ **Resolved
2026-09-06: the server, exclusively.** All three pauses — trick clear, meld
display, computer-move delay — are counted server-side and end with a published
event. The client holds no timing logic. See RT-8 through RT-11 and ARC-9.
*Consequences, which are substantial:*
- A pause becomes a state the game is *in*, not an effect the client draws. The
  round state machine gains a waiting state after each completed trick, during
  which the next lead must be rejected (RT-9). `Round.play_card` currently
  transitions straight to the next trick (D-13).
- The application layer needs a scheduler port (ARC-9) so that the domain can
  defer work without importing `asyncio`, and so tests can advance a virtual
  clock rather than sleeping (ARC-10).
- The reconnect snapshot must be able to express "paused, showing this trick"
  (RT-10), or a client reconnecting during a pause renders the wrong thing.
- The argument for client-owned trick clearing was that a server-driven clear
  forces the client to buffer animations. That concern disappears here: the
  server does not run ahead, so there is nothing to buffer.

**OQ-29 — Should there be a way to review the play so far?** ✅ **Resolved
2026-09-06: persistent public context, last-trick recall, and nothing more.**
See UI-14a, UI-14b, UI-14c.

The principle is to restore what a player at a physical table would have, and
no more. Three categories fall out of it:

- *Was public and stays available:* the contract, the auction winner, trump,
  the bid history, and each team's meld total. All were announced or laid on
  the table in front of everyone. Keeping them on screen costs nothing and
  players consult them constantly.
- *Was briefly available by convention:* the last trick. Asking to see it
  before it is turned is normal courtesy, and it also compensates for UI-15's
  1.5-second window, which is unforgiving if a player looks away. Earlier
  tricks are not reviewable — they are face-down on the table.
- *Was never available:* a running count of card points taken. Counting as the
  cards fall is a real skill, and displaying the total would quietly delete it.
  This is the one place the decision makes the game harder than it could be,
  deliberately. The totals appear in the round summary (FR-66) once play ends.

**OQ-31 — Is the dealer-selection draw worth building as an interaction?** ✅
**Resolved 2026-09-06: yes, keep it.** FR-11 is a stated requirement from
`prompt.md`, and "it is a little work for one moment per game" is not enough to
override it. Two things make it cheap: it needs only click, not drag (UI-8), so
it reuses the simplest affordance; and it is the first thing a player ever does,
in a position where nothing is at stake — which makes it the natural place to
teach the click-a-card gesture before it matters. Modelling the spread as 48
addressable positions over one deck (FR-11a) also makes FR-12's distinctness
hold by construction instead of by a retry loop.
*Note:* under FR-14 a tie restarts the whole draw, so this interaction can
repeat. It should stay quick.

**OQ-32 — Should `Player` carry a `team_id`?** ✅ **Resolved 2026-09-06: no,
derive it from the seat.** FR-4 makes partnership a pure function of position,
so storing it separately creates a state — North on the East/West team — that
is meaningless but constructible. See FR-4a.
*Consequence:* `Player.team_id` is removed (D-14) and
`Game.team_id_for_player` becomes a seat lookup. `Team` keeps its identity
because a team has a *name*, which is genuinely per-game data; what it loses is
a configurable id. This also removes the `_NS` / `_EW` string constants that
`GameService` currently carries.

**OQ-19 — How fast should computer players move?** ✅ **Resolved 2026-09-06:
about one second, configurable, reducible to zero for tests.** See FR-75c.
*Consequence:* the strategy is currently synchronous and stateless, called
inline. A delay means computer turns must be driven by a scheduled task rather
than resolved within the request that triggered them — which matters for the
SSE design, since the event for a computer's move arrives well after the HTTP
response to the human action that preceded it.

**OQ-20 — How strong should the computer player be?** ✅ **Resolved 2026-09-06:
meld-aware bidding and contract-aware passing.** Bidding values detected meld
plus a conservative trick estimate from aces and trump length; passing sends
trump and aces to a partner who won the auction rather than the four lowest
cards. See FR-75a and FR-75b.
*Consequence:* all three of the current strategy's methods are replaced.
`choose_play` — always play the highest legal card — was not raised as a
question and is retained, but it is weak: it spends aces on tricks already won
and never leads low to protect a partner. Worth revisiting once the rest works.

**OQ-21 — Should there be selectable difficulty levels?** ✅ **Resolved
2026-09-06: deferred.** One strategy, behind the existing replaceable
interface, so levels can be added later without touching the domain. See FR-75.

**OQ-22 — Must the server support multiple concurrent games?** ✅ **Resolved
2026-09-06: one game at a time.** The transport, tokens, and admin surface need
not accommodate concurrency, though the state port keeps its game-id keying.
See NFR-5.
*Consequence:* the computer-move scheduler and the SSE connection registry can
both be single-game structures, which simplifies them considerably.

**OQ-23 — Which Python web framework and push mechanism?** ✅ **Resolved
2026-09-06: FastAPI with Server-Sent Events.** Player actions go up as HTTP
requests; events come down a per-player SSE stream. See ARC-7. The browser's
built-in SSE reconnection covers much of RT-5, though the snapshot-on-reconnect
question (OQ-18) still stands.

**OQ-24 — Which client stack?** ✅ **Resolved 2026-09-06: TypeScript, no
framework.** Compiled with `tsc`, served as static assets, no bundler. See
ARC-8.

**OQ-25 — Is there any observability requirement?** ✅ **Resolved 2026-09-06:
log actions and events per game.** Every accepted action and published event,
plus rejections with their reason, tagged by game id. Hands and deals are
excluded so the log does not become a leak of private state — which also means
a game cannot be replayed exactly from the log alone. See NFR-9.
