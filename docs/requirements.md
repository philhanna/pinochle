# Pinochle — Requirements

**Status:** Current as of version 1.3.0
**Last updated:** 2026-09-24

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for a
web-based, four-player Pinochle game. It is the authoritative statement of
*what* the system does. It avoids prescribing *how*, except where an
architectural constraint is itself a requirement (see §4). How the system is
built is described in `docs/design.md`.

### 1.2 Scope

The system consists of:

- A **server-side application** written in Python that owns all game state and
  enforces all rules.
- A **browser-based client** written in TypeScript, one instance per human
  player, that renders the table from that player's point of view and submits
  that player's actions.
- An **administrator's console**, a separate browser page for creating,
  starting, repairing and abandoning a game.
- **Computer players** that can occupy any of the four seats and are driven by
  the server.

Out of scope for this release: user accounts and persistent player profiles,
matchmaking or lobbies beyond a single administrator-created game, ranking or
statistics, chat, durable storage, and mobile-native clients.

### 1.3 Definitions

| Term | Meaning |
| --- | --- |
| **Game** | A complete contest, played over multiple rounds, until a team reaches the winning score. |
| **Round** | One deal: deal → bid → trump → pass → meld → trick play → scoring. Dealer selection happens once per game, before the first round. |
| **Trick** | One cycle in which each of the four players plays exactly one card. |
| **Meld** | Scoring card combinations held in hand and exposed after the pass, before trick play. |
| **Contract** | The winning bid amount that the bidding team must meet or exceed. |
| **Going set** | Failing to make the contract. |
| **Tossing in** | The auction winner conceding the contract after seeing the meld, without playing it. |
| **Trump** | The suit named by the bid winner, which outranks all other suits for the round. |
| **Seat** | One of the four table positions: North, East, South, West. |
| **Partnership / Team** | Two players seated opposite each other: North+South (`NS`), East+West (`EW`). |
| **Dix** | The nine of the trump suit, worth meld points. |
| **Hold** | A pause the game occupies until any seated player releases it (RT-13). |
| **Notice** | The one-line announcement of what has just concluded (UI-19). |

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
- **FR-2a** A seat's designation shall be fixed when the game is set up. The
  only change permitted afterwards is the administrator handing a human seat
  to the computer (RT-12a); a computer seat is never handed to a person, and
  nothing hands a seat over automatically, however long its player is away.
- **FR-3** Players shall be assigned to the four seats North, East, South, and
  West. Turn order shall proceed clockwise: North → East → South → West →
  North.
- **FR-4** The four players shall form two partnerships of players seated
  opposite one another: North+South ("NS") and East+West ("EW").
- **FR-4a** Partnership membership shall be derived from the seat, never stored
  alongside it. The team identifiers `NS` and `EW` are fixed by the seating and
  are not configurable; a team's *name* is. It shall be impossible to represent
  a player seated North who belongs to East/West.
- **FR-5** Each player shall have a stable identifier, derived from the seat
  (`p-north`, `p-east`, `p-south`, `p-west`), and a human-readable display
  name.

### 2.2 Administrator

- **FR-6** An administrator shall create a game, which produces a unique game
  identifier.
- **FR-7** The administrator shall specify all four players in one request: for
  each, the display name, the seat, and whether the player is human or
  computer; and a display name for each of the two partnerships.
- **FR-7a** The console's setup form shall be pre-filled with a configured
  table — team names, and each seat's name and kind — read from the server's
  configuration (NFR-10). The values are only a starting point: the game is
  created from whatever the form holds when submitted. The built-in default is
  South human and the other three seats computer.
- **FR-8** The administrator may also be one of the players. The console and the
  player's table are separate pages with separate credentials.
- **FR-9** The administrator shall initiate play once four players and two
  teams are registered. The system shall reject the request to start unless
  exactly four players and two teams are registered.
- **FR-10** For each human player, game creation shall produce a join link
  containing the game identifier and an opaque, unguessable per-seat token. The
  link is returned once, at creation, and cannot be retrieved later. The
  administrator distributes the links. Opening a link shall seat the holder as
  that player.
- **FR-10a** The token shall be the sole credential for a seat. All player
  actions and the player's event stream shall be authorized by it, and the
  server shall serve a given player's hand only to the holder of that seat's
  token.
- **FR-10b** Every human seat shall have joined — have at least one open event
  stream — before play can begin; the start request shall be refused, naming
  the missing seat, until it has. Computer seats count as joined from the
  start. A seat whose player never opens their link may instead be given to
  the computer (RT-12a).
- **FR-10c** A seat token may drive several concurrent client connections. All
  of them shall show that seat's view and shall receive the same events, and
  any of them may act for the seat. Opening a seat in a second browser shall
  not disconnect the first.
- **FR-10d** The console shall accept its credential from the page address
  (`/admin?t=<token>`) as well as from a field on the page, so that an operator
  can open a link rather than copy a credential.

---

## 3. Game flow

The system shall enforce the following phase machine. Actions submitted for a
phase other than the current one shall be rejected with an error, and the game
state shall be left unchanged.

```
SETUP → DEALER_SELECTION → IN_ROUND [ round ]* → FINISHED

round: DEALING → BIDDING ─┬────────────────→ TRUMP → PASSING → MELDING ─┬─→ PLAYING → SCORING
                          │                                              │
                          ├─ CONFIRMING ─┬─→ TRUMP                       └─→ SCORING
                          │  (lone       │                                   (tossed in, FR-50b)
                          │   bidder,    └─→ ABANDONED (declined)
                          │   FR-32)
                          └─ ABANDONED (all four passed, FR-31)

ABANDONED → next round is dealt        SCORING → next round, or FINISHED (FR-67)
```

Two kinds of waiting stop the game:

- **A player's decision.** The lone bidder in `CONFIRMING`, the auction winner
  naming trump, each passer, each bidder, and each player in turn during play.
  None of these is timed.
- **A pause.** Either a *hold* that any seated player releases (RT-13) — after a
  tied draw, after the dealer is chosen, after a thrown-in hand, while the meld
  is on the table, and after each round is scored — or a *timed pause* counted
  by the server: the trick clear (UI-15) and a computer seat's move delay
  (FR-75c).

### 3.1 Dealer selection

- **FR-11** At the start of a game, a shuffled deck shall be presented
  face-down and spread out. Each of the four players shall select exactly one
  card from it. There is no turn order: any player who has not yet drawn may
  draw at any time.
- **FR-11a** The spread shall be modelled as 48 addressable positions over one
  shuffled deck. A player draws by clicking a face-down card in the spread,
  which reveals the card that lies at that position. A position already taken,
  a position outside the spread, and a second draw by the same player shall be
  rejected.
- **FR-11b** A computer player shall draw by choosing an untaken position at
  random, using the same operation a human draw reaches. Computer seats draw in
  clockwise seat order, so that a seeded game (NFR-7) is reproducible.
- **FR-11c** The spread shall be presented as a deck thrown across the table:
  the cards strewn irregularly over the inner portion of the felt rather than
  laid out in ranks, turned at differing angles, and lying across one another.
  Where each card lies is decided once per spread and does not change as
  others draw. A player shall be able to drag any card of the spread aside, to
  see or to reach what lies under it; a card so dragged stays where it is put
  and stays over what it was pulled off. Dragging a card moves it and shall not
  select it — selecting is the click of FR-11a. A card that lies under another
  is reached by moving what covers it, which is the deliberate overlap UI-18
  excepts.
- **FR-11d** A card once drawn shall leave the spread and be shown face up in
  front of its drawer's seat, where that player's hand is about to be dealt,
  for as long as the selection lasts.
- **FR-12** Each card may be selected by at most one player; the four drawn
  cards shall be four distinct physical cards from the same deck. FR-11a makes
  this hold by construction.
- **FR-13** The player drawing the highest rank shall become the dealer for the
  first round. At a table with a human seat, the result shall be held (RT-13)
  so the table can read who deals, and the first round shall be dealt when a
  seated player releases the hold.
- **FR-14** If two or more players tie for the highest rank, the entire
  selection shall be repeated — deck reshuffled, a fresh spread laid out, all
  four players drawing again, including those who did not tie — until a single
  player holds the highest card. Suit shall never break a tie. At a table with
  a human seat, the tied cards shall stay face up and be held (RT-13) until a
  seated player releases the hold, and only then shall the fresh spread be laid
  out.
- **FR-15** Each player's drawn card shall be revealed to all players.
- **FR-16** After each round, including an abandoned one, the deal shall pass
  to the next player clockwise. Dealer selection shall not be repeated during a
  game.

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
- **FR-21a** The server delivers each hand whole. The client shall present the
  deal as it happens at a table — one packet of three at a time, clockwise from
  the dealer's left — before the round can be acted on. This presentation is
  cosmetic: it changes nothing in the game, and frames that arrive during it
  are applied, in order, when it finishes.
- **FR-22** A player shall see only their own hand. The other three hands shall
  never be transmitted to a client that does not own them.
- **FR-23** A player's hand shall be displayed grouped by suit in the order
  Spades, Hearts, Clubs, Diamonds, and within each suit descending by rank
  (Ace, Ten, King, Queen, Jack, Nine). The suit groups shall alternate between
  black and red, so that the seam between two suits in a fanned hand (UI-4) can
  be seen rather than read.
- **FR-23a** Once trump is named, the trump suit shall move to the leftmost
  position and the other three shall follow it, the colours still alternating.
  Where either suit of the required colour would serve, the one earlier in
  FR-23's order shall come first — so the four orders are ♠♥♣♦, ♥♠♦♣, ♣♥♠♦ and
  ♦♠♥♣. This is the only reordering by suit during a round; the re-sort shall
  be made visible so cards do not appear to teleport. Cards received in the
  pass are sorted into place.

### 3.4 Bidding

- **FR-24** Bidding shall proceed clockwise, beginning with the player to the
  dealer's left.
- **FR-25** On their turn a player shall either place a bid or pass.
- **FR-26** A bid shall be an integer multiple of 10.
- **FR-27** The first (lowest legal opening) bid shall be at least 250.
- **FR-28** Each subsequent bid shall be strictly greater than the current high
  bid. Since all bids are multiples of 10, the minimum raise is 10. There shall
  be no upper limit on a bid.
- **FR-29** A player who passes shall be removed from the remainder of the
  bidding for that round and shall not bid again.
- **FR-30** Bidding shall end when three players have passed and a bid has been
  placed. The remaining player wins the auction at their last stated bid, which
  becomes the contract. If the first three players all pass, the fourth still
  gets a turn, and may open or pass.
- **FR-31** If all four players pass without any bid being placed, the round
  shall be abandoned. No score shall change, and the deal shall pass to the
  next player clockwise. At a table with a human seat the thrown-in hand shall
  be announced and held (RT-13), and the next round shall not be dealt until a
  seated player releases the hold. An all-computer table deals on at once.
- **FR-32** If exactly one player places a bid and the other three all pass,
  that player — whoever they are — shall be offered the option to decline the
  contract, and the table shall be told that the offer is being considered. If
  they decline, the round shall be abandoned with no score change and the next
  round dealt at once, without a hold. If they accept, they win the auction at
  their bid. A player who was outbid and later inherits the auction because
  everyone else passed is not a lone bidder and gets no such option.
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
  winner's team and shall not be visible to the opposing team. Everyone shall
  see that four cards changed hands, since hand sizes are public (UI-5).
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
  be identified from their 12-card hand and the cards that make it exposed
  face-up on the table in front of them, grouped by combination. A card that
  serves several combinations is laid down once.
- **FR-45** Each player's meld, and each team's meld total, shall be displayed
  to all players.
- **FR-46** Meld shall be scored from the hands **as they stand after the
  pass**. Meld points shall be recorded at this moment and shall not be
  recomputed later, since the cards leave the hand during trick play.
- **FR-47** The following combinations shall be recognized, with the doubled
  column applying when the player holds both copies of every card involved:

  | Combination | Cards | Points | Doubled |
  | --- | --- | --- | --- |
  | Run | A-10-K-Q-J of trump | 150 | 1500 |
  | Royal marriage | K-Q of trump | 40 | 40 per pair |
  | Marriage | K-Q of a non-trump suit | 20 | 20 per pair |
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
  combine. A team's meld is the sum of two independent detections.
- **FR-49** Each run shall consume one trump King and one trump Queen. Any trump
  King-Queen pair remaining after the runs have been accounted for shall score
  a royal marriage. A hand holding a run plus a spare trump K-Q therefore
  scores 150 + 40 = 190.
- **FR-50** Meld shall be computed by the server from the player's hand. A
  player shall not declare or claim their own meld.
- **FR-50a** Once the meld is exposed, the game shall wait, with no timer,
  before the first trick is led. At a table with a human seat this wait is a
  hold (RT-13): any seated player may release it, and releasing it begins play
  with the auction winner leading. The auction winner's own Play control
  releases that same hold. A direct request to begin play while the hold
  stands shall be refused. At an all-computer table there is no hold, and the
  auction winner begins play.
- **FR-50b** While the meld is on the table the auction winner, and only the
  auction winner, shall be offered a second option: to **toss the contract
  in** rather than play it out. This is the first point at which they have seen
  both their final twelve cards and every exposed meld. Tossing in ends the
  meld hold and scores the round at once.
- **FR-50c** When a contract is tossed in, the contract amount shall be
  deducted from the bidding team's cumulative score and the opposing team shall
  add their meld. Neither side scores trick points and no last-trick bonus
  arises, because no trick is played.
- **FR-50d** Tossing in therefore costs the bidding team **less** than playing
  on and going set, which forfeits the contract *and* their meld (FR-63).

### 3.8 Trick play

- **FR-51** The auction winner shall lead the first trick.
- **FR-52** Play within a trick shall proceed clockwise from the leader. Each
  player shall play exactly one card.
- **FR-53** The following play restrictions shall be enforced in order, and the
  server shall reject any card that violates them:
  1. If the player holds one or more cards of the led suit, they shall play a
     card of the led suit; and if they hold a card of the led suit that beats
     the highest card of the led suit already played, they shall play such a
     card.
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
- **FR-64** The non-bidding team shall add their meld plus their trick points
  to their cumulative score, **unless their trick points for the round are
  zero**, in which case they shall score zero for the round (meld included).
  Trick points are zero when the team took no trick; they are also zero for a
  team whose tricks held only Jacks and Nines and did not include the last.
- **FR-65** Cumulative scores may go negative.
- **FR-66** After each round the system shall display, for both teams: meld,
  card points, last-trick bonus, round total, the points actually applied, and
  the new cumulative score; and shall state whether the auction-winning team
  made the contract, went set, or tossed it in. At a table with a human seat
  the summary shall be held (RT-13), and the next round shall not be dealt
  until a seated player releases the hold.

### 3.10 Ending the game

- **FR-67** The game shall end as soon as a team's cumulative score reaches or
  exceeds **2000** points, evaluated at the end of a round. A score of exactly
  2000 wins.
- **FR-68** If exactly one team is at or above 2000, that team wins.
- **FR-69** If both teams are at or above 2000 after the same round, the
  auction-winning team of that round wins.
- **FR-70** If neither team is at or above 2000, a new round shall begin with
  the deal passing clockwise.
- **FR-71** The result, with both final scores, shall be announced to all four
  players, and the game shall accept no further play actions. The round that
  ends the game shall first be summarised and held exactly as any other round
  is (FR-66), and the result announced only when a seat releases that hold.
  At an all-computer table the result follows at once.

---

## 4. Architecture

- **ARC-1** The server shall follow a ports-and-adapters (hexagonal)
  architecture. The domain and application layers shall contain no dependency
  on web frameworks, transport, storage technology, or presentation.
- **ARC-2** The server shall be the sole authority on game state and rules. The
  client shall be a rendering and input surface only; no rule shall be enforced
  solely on the client. The client is told which actions are open to it rather
  than deriving them.
- **ARC-3** Each port shall be a single abstract base class in its own module,
  named after the class in snake_case. Domain models shall likewise have their
  own modules, except that closely related types may share one: the domain
  events and the game's phase enumeration live with the `Game` aggregate,
  `PlayerType` and `Position` with `Player`, and `HoldReason` with `Hold`.
- **ARC-4** Ports shall be defined with `abc.ABC` and `@abstractmethod`.
- **ARC-5** The system shall expose driving ports for administrative use cases
  (`AdminPort`) and for player actions (`PlayerActionPort`), and driven ports
  for state persistence (`GameStatePort`), player notification
  (`NotificationPort`), deferred execution (`SchedulerPort`), seat credentials
  (`SeatTokenPort`), and card image resolution (`CardImagePort`).
- **ARC-6** Game state persistence shall be behind a port so that the in-memory
  implementation can be replaced without changing domain or application code.
- **ARC-7** The server shall be built on **FastAPI**. Player actions and
  administrative commands shall be submitted as ordinary HTTP requests; state
  changes shall be pushed to clients over **Server-Sent Events**, one stream
  per connection. The SSE endpoint is a driving adapter over the notification
  port and shall contain no game logic.
- **ARC-8** The browser client shall be written in **TypeScript with no UI
  framework**, compiled with `tsc` and served as static ES modules. No bundler
  and no runtime dependency shall be required to run it. Browser code shall
  live under `frontend/`, separate from the Python package; the card artwork is
  the one browser-facing asset that ships inside the Python package, served
  over HTTP through `CardImagePort`.
- **ARC-9** Deferred execution shall be reached through a driven port — a
  scheduler that accepts "invoke this after *n* seconds". The domain and
  application layers shall express delays through that port and shall not
  import `asyncio`, `time.sleep`, or any other concrete timing mechanism. The
  production adapter is asyncio-based; tests shall use a fake that advances a
  virtual clock on demand.
- **ARC-10** No automated test shall wait in real time for a game pause. A test
  that exercises a timed transition shall advance the fake scheduler instead.

---

## 5. User interface

- **UI-1** Each player's browser shall render the table from that player's own
  seat, drawn at the bottom of the screen. The other three players shall appear
  to the left, across, and to the right, matching their true clockwise
  relationship: the seat that plays next sits to the left.
- **UI-2** The table background shall be a green felt surface, resembling a
  physical card table.
- **UI-3** Each player's name shall be displayed at their seat, marked when
  that seat is the dealer. The partnerships shall be visually distinguishable
  by colour, computer-played seats shall be distinguishable from human ones,
  and during the auction each seat shall show its latest call.
- **UI-4** The viewing player's own hand shall be shown face-up, fanned, and
  ordered per FR-23.
- **UI-5** The other three hands shall be shown as fanned card backs, with the
  correct number of cards remaining.
- **UI-6** The centre of the table shall be the trick area. Each played card
  shall be positioned nearer the player who played it, so that all four cards
  of the trick are simultaneously visible and attributable.
- **UI-7** The player whose turn it is shall be clearly indicated to everyone,
  both at their seat and in a status line.
- **UI-8** A human player shall play a card either by dragging it from their
  hand to the centre of the table, or by clicking it. The two gestures shall be
  exactly equivalent. The same pair of gestures shall apply to the pass: a card
  moves from the hand to the pass tray by click or drag, and back again the
  same two ways.
- **UI-9** The client shall visually distinguish cards that are legal to play
  from those that are not, and shall refuse to submit an illegal play. Which
  cards are legal comes from the server (ARC-2).
- **UI-10** The bidding interface shall let a player enter a bid, starting at
  the current minimum and adjustable by +10 and +50, or pass. Amounts that are
  not a multiple of 10 at or above the minimum shall be refused before they are
  sent. The running bid history shall be shown.
- **UI-10a** A lone bidder (FR-32) shall be offered Accept and Decline.
- **UI-11** The trump-naming interface shall let the auction winner choose one
  of the four suits.
- **UI-12** The passing interface shall let a player move exactly four cards
  into a pass tray and confirm; confirmation is disabled until four are
  chosen. The cards received, and those sent, shall be shown to the passing
  team only.
- **UI-12a** While the meld is on the table the auction winner shall be shown
  their side's meld and how much more is needed in cards to make the contract,
  with Play and Toss-in controls (FR-50a, FR-50b).
- **UI-13** Exposed meld shall be displayed face-up in front of each player,
  grouped by combination, for as long as the meld is on the table.
- **UI-14** A scoreboard shall show both teams' cumulative scores, the round
  number, the contract and its bidder, the trump suit, and the score being
  played to. It may be collapsed to a single control and reopened.
- **UI-14a** The scoreboard shall additionally retain, for the whole round, the
  bid history and each team's meld total — the latter remaining visible after
  the exposed meld has been cleared from the table. Each player's meld
  combinations are named on the scoreboard until the first trick is gathered.
- **UI-14b** The last completed trick shall be viewable on demand for the
  duration of the following trick. Tricks before that one shall not be
  reviewable.
- **UI-14c** Each team's tricks taken shall be shown face down as a stack, in
  the size of the cards drawn for the deal, with the cumulative card points of
  those tricks on the back of the stack. North-South's stack lies to the left of
  North's hand and East-West's below West's, wherever those seats fall on the
  table. The last-trick
  bonus is not included: it appears only in the round summary of FR-66.
- **UI-15** A completed trick shall remain visible for a fixed, configurable
  interval — 1.5 seconds by default — and shall then be cleared automatically
  to the winner. Clearing shall not require any player action. The interval
  shall be counted by the server, which publishes an event when the trick is
  cleared (RT-8). The clearing shall be shown as an animation: the four cards
  are gathered into one pile, turned face down and carried to the winning
  team's stack. It is cosmetic and client-side, and is omitted when the player
  prefers reduced motion.
- **UI-16** Card artwork shall be served by the server for both faces and
  backs, in SVG and in 96-dpi PNG. Faces shall be addressed by the same
  two-character card code the event stream uses. The card back shown on the
  table shall be chosen by configuration (NFR-10) from the bundled set.
- **UI-17** The interface shall be usable on current desktop versions of Chrome
  and Firefox. The table is a fixed layout scaled to fit the window rather than
  a responsive one, so that four windows tiled on one monitor each show a
  whole table. Tablet and phone support are not requirements.
- **UI-18** Every control the interface presents as available shall receive the
  clicks aimed at it. A control that is drawn and enabled shall be reachable
  where it is drawn, with nothing positioned over it that takes the click
  instead; the same shall hold for the regions a card may be dragged onto
  (UI-8). This shall hold throughout a round and at every window size the
  layout supports (UI-17). The scattered spread of FR-11c is the one
  exception: its cards lie across one another by design, and what must hold
  there is that cards enough to draw from are reachable, not that every card
  is.
- **UI-19** The interface shall present a notice area that states, one sentence
  at a time, the outcome of each stage of play as it concludes: who deals, a
  tied draw, a lone bidder considering their bid, who won the auction and at
  what, which suit is trump, who takes each trick, that everyone passed, that
  the meld is to be reviewed, a toss-in, how the round scored, and who won the
  game. Each notice replaces the one before it. The announcements made before
  the first card is led end when it is played. A notice is public: all four
  seats shall see the same words at the same moment (RT-11).
  The wording shall be composed by the client from the events it has already
  received, and shall not be sent as text by the server. Every fact a notice
  states is already published as an event, and the event is the authoritative
  copy of it.
  There shall be no scrolling history of notices. What deserves to outlive its
  moment is named by UI-14a and belongs on the scoreboard.
- **UI-19a** A notice shown while the game is held for a player (RT-13) shall
  present the control that releases the hold — a Continue button — within the
  notice itself. Any seated player may use it. A notice shown during a timed
  pause shall offer no such control.
  The notice area is not the turn indicator of UI-7, nor the report of a
  refused action (NFR-4), which is shown briefly and only to the seat that
  attempted it, nor the stream-status indicator of RT-5b.
- **UI-20** When a round has been scored the centre of the table shall show the
  round summary of FR-66, and when the game is over, the final result.

---

## 6. Real-time behaviour

- **RT-1** Each client shall see only the information its player is entitled
  to: their own hand, public events, and team-private information (the pass)
  where applicable. Private state shall be filtered on the server, not hidden
  on the client.
- **RT-2** State changes shall be delivered to clients by server push. Clients
  shall not poll for state, and the response to an action shall carry no game
  state.
- **RT-3** The display shall update as soon as a play is made, without
  requiring user action.
- **RT-4** The following events shall be published: the game configured, a
  dealer-selection spread laid out, each draw, a tied draw, the dealer
  selected, a round started, cards dealt (per player, privately), each bid or
  pass, a lone bidder's offer, a round abandoned, trump named, cards passed (to
  the passing team only), meld exposed (per player), play begun, a contract
  tossed in, a computer seat's delay begun, each card played, a trick
  completed, a trick cleared, the acting seat's prompt (privately), a round
  scored, game over, a hold begun, a hold ended, a seat handed to the
  computer; and, from the transport rather than the game, a seat's stream lost,
  a seat's stream regained, and the game abandoned by the administrator.
- **RT-5** A client builds its view from the event stream alone. The server
  shall not construct a point-in-time snapshot of a game in progress; there is
  one authoritative history, and it is the sequence of events.
- **RT-5a** A client that loses its stream shall be able to resume it. Every
  frame carries a sequence number; on reconnecting, a client shall present the
  last one it received, and the server shall replay the frames that seat
  missed — its own private frames and the table's broadcasts, never another
  seat's — before resuming live delivery. A client opening a seat afresh, such
  as a second tab or a reopened join link, is replayed the game from the
  beginning in the same way. Replay is bounded: where the server can no longer
  reach back far enough, it shall say so rather than deliver a history with a
  hole in it, and the client shall mark its view as partial.
- **RT-5b** A client shall show whether its stream is live, and shall not
  submit actions while it is not. A table that has stopped being told what
  happens is frozen, not merely quiet, and shall not be presented as playable.
- **RT-6** Computer players' actions shall be produced by the server and
  published through the same event stream as human actions, so that clients
  need not distinguish between them.
- **RT-7** A computer player's move shall be delayed slightly so that human
  players can follow the play, and the table shall be shown which seat is
  thinking. See FR-75c.
- **RT-8** Every pause in the game — the trick-clear interval (UI-15), the
  computer-move delay (FR-75c), and every hold (RT-13) — shall be owned by the
  server. The client shall hold no timer that affects the game: it renders the
  state it was last told about and changes only when an event tells it to. The
  client's only timers are presentational — the visible deal (FR-21a), the
  fading of a refused-action message, and similar — and none of them decides
  or delays a game action.
- **RT-9** A pause is therefore a real state the game occupies, not a
  presentation effect. While the game is paused, player actions that would
  advance past the pause shall be rejected exactly as any other out-of-phase
  action (NFR-4); the next leader shall not be able to play before the
  completed trick has been cleared.
- **RT-10** A pause shall be delimited by events — one marking its start and
  one its end — rather than inferred by the client from a clock. The trick
  clear runs from `trick_completed` to `trick_cleared`; a computer's delay from
  `seat_thinking` to the action it takes; a hold from `hold_begun` to
  `hold_ended`. Every frame also carries the current phase, the seat on the
  clock, and any pause or hold in force, so that a client that missed the
  opening event still learns of the pause from the next frame.
- **RT-11** Because all four clients are driven from one clock, they shall
  display the same phase at the same time, to within network latency.
- **RT-12** Nothing acts for a seat whose player is absent (FR-2a), so play
  blocks there until they return. A seat that reconnects resumes and play
  continues (RT-5a); one that does not leaves the table waiting, and the game
  is then finished only by giving that seat to the computer (RT-12a) or by the
  administrator abandoning it. The server shall publish, to the whole table and
  to the administrator, when a seat's last stream closes and when a stream
  opens for a seat that had none; the console's seat board shall reflect both
  without being refreshed by hand.
- **RT-12a** A seat whose player has gone shall be able to be given to the
  computer, and the game shall carry on from where it stopped. The
  administrator shall be able to do two things to a human seat: unlink its
  player, which stops that player's credential working and ends the streams
  opened with it; and seat a computer in their place, which also unlinks the
  player and is available whether the player was unlinked, dropped their
  connection, or never joined at all.
  The seat is replaced, never re-created. It keeps its identity, its name, its
  place at the table, its partnership and the cards in its hand, so a round in
  progress resumes at the exact point it stopped; if the seat was the one on
  the clock, the computer plays it as it would any other (RT-6, RT-7). The
  table shall be told that the seat has changed hands, and shall mark it as
  computer-played thereafter (UI-3).
  Seating a computer in the last human seat leaves a table that can no longer
  release a hold, so any hold then awaiting release shall end at once, by
  RT-13's rule for a table with nobody at it.
  Neither action applies to a computer seat, and a computer cannot be seated
  once the game is over.
- **RT-12b** The administrator shall be able to abandon a game, giving a reason.
  The game is marked finished, the table and the console are told, and every
  seat token for the game is revoked.
- **RT-13** A *hold* is a named pause the game occupies, owned by the server
  (RT-8) and delimited by published events (RT-10). The holds are:

  | Hold | Begins | Releasing it |
  | --- | --- | --- |
  | Draw tied | after a tied dealer draw (FR-14) | lays out a fresh spread |
  | Dealer selected | once the dealer is settled (FR-13) | deals the first round |
  | Round abandoned | after all four pass (FR-31) | deals the next round |
  | Meld exposed | once the meld is on the table (FR-50a) | begins play |
  | Round scored | after each round's summary (FR-66) | deals the next round, or announces the result (FR-71) |

  A hold shall be released by any one seated player. It shall not require all
  four, and it shall not require the administrator.
  Releasing a hold shall be idempotent and shall name the hold it releases. A
  release naming a hold that has already ended shall succeed and change
  nothing, rather than being reported to the player as a failure.
  A hold shall wait indefinitely; it shall not also be given an interval after
  which it ends by itself. Computer seats never release a hold and take no
  action while one stands.
  A hold shall be taken only at a table that has at least one human seat.
  Where every seat is a computer there is nobody to read what the hold is
  showing and nobody who could ever end it, so such a table shall proceed as
  though the hold had been released at once. The test is the seat's kind, not
  whether its player is presently connected.
  The trick clear and the computer delay are *timed pauses*, not holds: they
  carry no identifier, end by themselves, and cannot be released.

---

## 7. Computer player

- **FR-72** A computer player shall be able to perform every action a human can:
  draw for the deal, bid or pass, accept a lone contract, name trump, select
  cards to pass, begin play, and play a card.
- **FR-73** A computer player shall never make an illegal move.
- **FR-74** A computer player shall base its decisions only on information its
  seat is entitled to. It shall not read other players' hands. Its strategy is
  given only a view of what its seat may see.
- **FR-75** The decision logic shall be replaceable, so that strategies of
  different strength can be swapped in. The system ships exactly one strategy;
  selectable difficulty levels are out of scope for this release.
- **FR-75a** The computer player shall bid on the basis of what its
  *partnership* can score. For each suit as prospective trump, it values its
  own detected meld plus a trick estimate of 15 per ace of that suit and 10 per
  card of that suit beyond four; it takes the best suit's figure and adds a
  fixed allowance of 180 for its partner's contribution. It bids one increment
  at a time — 250 to open, otherwise 10 above the current high — and passes
  once the next bid would exceed its valuation.
- **FR-75b** When passing, the computer player shall pass all its trump first,
  highest first; then aces; then its lowest remaining cards. Cards that
  complete its own non-trump meld — marriages, pinochle, and any
  arounds — are kept back, and released lowest first only when fewer than four
  cards would otherwise be available. The auction winner passing back uses the
  same selection.
- **FR-75c** A computer player's action shall be delayed by a configurable
  interval, defaulting to one second, so that human players can follow the
  play. The delay shall be reducible to zero so that all-computer games can be
  run at full speed.
- **FR-75d** A computer player shall stop bidding against its own partner. Once
  both opponents have passed and both partners are still bidding, the partner
  who has bid fewer times passes — unless it holds a whole run, in which case
  it may bid once more to take the contract and name that suit.
- **FR-75e** A computer player shall name as trump the suit in which it holds
  the most cards; shall play the highest-ranked of its legal cards; shall
  always accept a lone contract; and shall always play a contract out rather
  than toss it in.

---

## 8. Non-functional requirements

- **NFR-1** The server shall target Python 3.12 or later.
- **NFR-2** All optional and development dependencies shall be declared in
  `[project.dependencies]` in `pyproject.toml`, so that `pip install -e .` is
  sufficient to run the tests.
- **NFR-3** Server unit tests shall use pytest. Domain rules — bidding validity,
  meld detection, trick resolution, and round scoring — shall be covered by
  tests that do not require a running server or browser. The client's pure
  modules — the reducer, hand ordering, layout, notices and view text — shall
  be covered by tests run under Node without a browser; control reachability
  (UI-18) is checked separately in a real browser.
- **NFR-4** An action submitted by the wrong player, at the wrong time, or with
  invalid arguments shall be rejected with a clear error, and the game state
  shall be left exactly as it was. The client shall show the server's own
  message.
- **NFR-5** The system shall support one game in progress at a time. Running a
  second game concurrently is not a requirement, and the transport, seat
  tokens, and administrative surface need not accommodate it. The game-id
  keying of the state port shall nevertheless be retained.
- **NFR-6** The server shall not transmit a player's hand to any other player's
  client, nor to the administrator's console, under any circumstances.
- **NFR-7** Randomness used for shuffling, and for the computer players' draws
  for the deal, shall be seedable so that a game can be reproduced.
- **NFR-8** Game state shall be held in memory only, behind `GameStatePort`. A
  server restart loses a game in progress; no durable storage is required for
  this release.
- **NFR-9** The server shall log, at a level that can be changed without a code
  change, every published event tagged with the game id and its recipient;
  every refused credential, with the path; and every stream opened and closed.
  Hands, passed cards and tokens shall not be logged, so that the log is not
  itself a leak of private state.
- **NFR-10** The server shall be configured from `PINOCHLE_*` environment
  variables, which may also be supplied in a `.env` file; a variable already in
  the environment wins over the file. An invalid value for a setting that is
  checked at startup — a seat kind, a card-back name — shall stop the server
  from starting rather than be silently ignored.
- **NFR-11** The system shall be deployable as a single container image that
  holds both the server and the compiled client and contains no Node runtime.
  The server shall run as exactly one worker process.
