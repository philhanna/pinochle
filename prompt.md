# Build prompt: a four-player web Pinochle game

You are building, from an empty repository, a web-based four-player partnership
Pinochle game: a Python server that owns every rule and all state, a browser
client (one per human player) that renders the table from that player's seat,
an administrator's console, and server-driven computer players. This document
is the whole specification. Where it gives an exact number, string, name or
format, use it exactly: the client, the server and the tests depend on each
other through those details.

Work in slices, keeping the test suite green after each one (see §12 for the
order). Do not stop at a skeleton: the finished result plays complete games,
all-computer and mixed, in a browser.

---

## 1. Stack and hard constraints

- **Server:** Python ≥ 3.12, FastAPI, uvicorn, python-dotenv. No SSE library;
  SSE is a `StreamingResponse` over an async generator. No database.
- **Client:** TypeScript with **no UI framework, no bundler, no runtime
  dependency**. `tsc` compiles `frontend/src/*.ts` to `frontend/dist/*.js` ES
  modules that the browser loads natively. Every relative import is written
  with a `.js` extension. `typescript` is the only devDependency.
- **Architecture:** hexagonal (ports and adapters). The domain and application
  layers never import FastAPI, Starlette, `asyncio`, `time`, `json`, or
  anything under `adapters/` or `web/`.
- **One process, one worker, one asyncio loop.** State is in memory. Every
  route handler is `async def`. Because everything runs on one thread, each
  service operation is atomic by construction; there are no locks.
- **Server is sole authority.** The client never computes a rule. It is told
  whose turn it is, which cards are legal, the minimum bid, and when the game
  is paused.
- **Push, not poll.** Commands are HTTP POSTs that return `204 No Content`;
  every state change reaches clients only as SSE frames. There is no GET
  endpoint returning game state, and the server never builds a snapshot: the
  event sequence is the only history.
- **No test waits in real time.** Every delay goes through a `SchedulerPort`;
  tests use a fake scheduler with a virtual clock.

### Coding conventions (mandatory)

- Each port is one `abc.ABC` with `@abstractmethod`s in its own module, named
  after the class in snake_case (`game_state_port.py` → `GameStatePort`). Never
  `typing.Protocol`.
- Each domain model has its own module named after the class
  (`team_round_score.py` → `TeamRoundScore`). Exceptions: all domain events and
  `GamePhase` live in `game.py` with `Game`; `PlayerType` and `Position` live
  with `Player`; `HoldReason` with `Hold`.
- The first line of every `__init__.py` (in `pinochle/` and `tests/`) is a
  comment with its dotted package name, e.g. `# pinochle.adapters`. Other
  modules start with a similar `# pinochle.domain.meld` comment line.
- In a module, main functions come first, followed by the functions they call
  in order of first mention, recursively. In a class, `__init__` first, then
  what it calls, recursively.
- Tests use pytest (`asyncio_mode = "auto"`). All dependencies, test tools
  included, go in `[project.dependencies]` so `pip install -e .` is enough:
  `pytest, pytest-mock, pytest-asyncio, fastapi, uvicorn[standard], httpx,
  python-dotenv`.
- Docstrings and comments cite requirement ids (FR-n, UI-n, RT-n) from this
  document where a rule is being implemented.

---

## 2. Repository layout

```
pyproject.toml            # setuptools; packages.find include ["pinochle*"]; pytest testpaths=["tests"], addopts="-q"
Makefile                  # §11
README.md  CHANGELOG.md  LICENSE (MIT)  .env.example  .gitignore  .dockerignore
pinochle/
  domain/
    cards/ card.py rank.py suit.py deck.py __init__.py
    bid.py errors.py game.py hand.py hold.py meld.py player.py
    scoring.py team.py team_round_score.py trick.py
  ports/     admin_port.py player_action_port.py game_state_port.py notification_port.py
             scheduler_port.py seat_token_port.py card_image_port.py
  services/  game_service.py round.py computer_driver.py seat_view.py
  strategies/ computer_player_strategy.py
  adapters/  in_memory_game_state.py sse_notification.py logging_notification.py
             composite_notification.py print_notification.py asyncio_scheduler.py
             fake_scheduler.py immediate_scheduler.py in_memory_seat_tokens.py svg_card_image.py
  web/       main.py container.py dependencies.py security.py errors.py card_codec.py
             event_encoder.py turn_header.py sse_stream.py transport_events.py schemas.py
             routers/ admin.py player.py stream.py cards.py
  card_images/ fronts/ (+ png_96_dpi/)  backs/ (+ png_96_dpi/)  other/   # each dir has an __init__.py
  app.py     # small headless wiring: ImmediateScheduler + PrintNotification, no driver
frontend/
  package.json tsconfig.json .gitignore(dist, node_modules)
  public/ index.html admin.html table.css style.css      # served at /assets/
  src/    main.ts admin.ts types.ts stream.ts token.ts api.ts actions.ts state.ts cards.ts
          layout.ts view.ts notice.ts deal.ts sweep.ts table.ts hand.ts spread.ts panels.ts log.ts
  dist/   # tsc output, git-ignored, served at /static/
  test/   *.test.js (node --test against dist/), fixtures/seat-stream.json, browser/reachability.html
tests/    # mirrors pinochle/: domain/ ports/ adapters/ services/ strategies/ web/ (with conftest.py)
scripts/  dev.sh seed.py record_frames.py hit_test.py
docker/   Dockerfile compose.yaml
docs/     requirements.md design.md docker-usage.md
```

**Card artwork** (UI-16) ships inside the Python package and is not generated:
copy an SVG card deck into `pinochle/card_images/`. Faces are
`fronts/<suit>_<rank>.svg` with suit `spades|hearts|clubs|diamonds` and rank
`9|10|jack|queen|king|ace` (the deck may also contain 2–8 and jokers; they are
unused). Backs are `backs/<name>.svg`; the bundled set is `abstract,
abstract_clouds, abstract_scene, astronaut, blue, blue2, cars, castle, fish,
frog, red, red2`. Each directory has a `png_96_dpi/` sibling holding the same
names as 96-dpi PNGs. Include the directories as package data.

---

## 3. Game rules (what the server enforces)

### 3.1 Seats, teams, players

- Exactly four players at seats `NORTH, EAST, SOUTH, WEST`. Clockwise turn
  order N → E → S → W → N.
- Teams are derived from seat, never stored: `NS` (North+South) and `EW`
  (East+West). `Position.team_id` computes it. Team *names* are configurable.
- Player ids are derived from seat: `p-north`, `p-east`, `p-south`, `p-west`.
  Each player has a display name and a `PlayerType` of `HUMAN` or `COMPUTER`.
- A seat's type is fixed at setup. The only change is the administrator handing
  a human seat to the computer (`seat_computer`), which keeps id, name, seat,
  team and hand. A computer seat never becomes human.

### 3.2 Deck and ranks

- 48 cards: two copies each of 9, J, Q, K, 10, A in four suits. The two copies
  are equal (`Card` equality is by rank and suit).
- Rank order low→high: 9 < J < Q < K < 10 < A.
- `Deck.shuffle(rng)` takes an optional `random.Random` (seedable, NFR-7).

### 3.3 Phase machine

```
Game:  SETUP → DEALER_SELECTION → IN_ROUND [round]* → FINISHED
Round: DEALING → BIDDING ─┬──────────────→ TRUMP → PASSING → MELDING ─┬→ PLAYING → SCORING
                          ├ CONFIRMING ─┬→ TRUMP                       └→ SCORING (tossed in)
                          │ (lone bidder)└→ ABANDONED (declined)
                          └ ABANDONED (all four passed)
```

Any action out of phase raises `WrongPhaseError`; by the wrong seat,
`NotYourTurnError`; with bad arguments, `IllegalActionError`. The state is left
exactly unchanged on any error (validate before mutating).

### 3.4 Dealer selection (once per game)

- A shuffled 48-card deck is laid face-down as a spread of 48 addressable
  positions. Any undrawn player may draw at any time (no turn order) by
  choosing a position; that card is revealed to everyone. Taken position, out
  of range, or a second draw by the same player → `IllegalActionError`.
- The spread (`_DealerSpread`: the 48 cards and who drew which position) is
  transient state held by `GameService`, not by `Game`. Its absence is the
  phase check for drawing.
- Highest rank deals. Suit never breaks ties. On a tie for highest, the whole
  selection repeats: reshuffle, new spread, all four draw again.
- Computer seats draw a random untaken position using the shared seeded RNG,
  in clockwise seat order (reproducibility).
- After each round (including an abandoned one) the deal passes clockwise.

### 3.5 Deal

- Shuffle before each deal. Deal three at a time, clockwise from the dealer's
  left, until 12 each. Each hand is sent privately to its owner only.

### 3.6 Bidding

- Clockwise from the dealer's left. Bid or pass. Bids are multiples of 10;
  opening bid ≥ 250 (`MINIMUM_BID`); each bid > current high
  (`BID_INCREMENT = 10`); no maximum. A pass removes the player from the
  auction.
- Ends when one bidder remains after at least one bid; that player wins at
  their last bid (the contract). If the first three pass, the fourth still
  gets a turn.
- All four pass → round `ABANDONED`, no score change, deal rotates.
- Exactly one player bid and three passed (a *lone bidder*) → phase
  `CONFIRMING`: that player accepts (becomes auction winner) or declines
  (round abandoned, next round dealt at once with no hold). A player who was
  outbid and later inherits the auction is not a lone bidder.
- `BiddingRound` holds `history: list[BidEntry(player_id, amount|None)]`,
  `current_high`, `high_bidder`, `active_players`, `current_bidder`,
  `is_over`, `bid_count`.

### 3.7 Trump, pass, meld

- Only the auction winner names trump (`TRUMP` phase).
- `PASSING`: the partner passes exactly four cards from their hand to the
  auction winner (who now holds 16), then — strictly after — the auction
  winner passes four back. Out-of-order → `WrongPhaseError`/`NotYourTurnError`;
  not exactly four held cards → `IllegalActionError`. The opponents never pass.
  Passed cards are visible only to the two partners.
- Once both passes are in, meld is detected and recorded for all four hands
  (never recomputed). Phase `MELDING`; `Round.current_player` is the auction
  winner.

**Meld detection** (`detect_meld(cards, trump) -> list[MeldUnit(name, points, cards)]`),
per hand, never across hands; a team's meld is the sum of its two players':

| Unit name(s) | Cards | Points |
| --- | --- | --- |
| `Run` / `Double Run` | A-10-K-Q-J of trump (both copies of all five for double) | 150 / 1500 |
| `Royal Marriage` | K-Q of trump, *after* each run consumes one trump K and Q | 40 × pairs |
| `Marriage` | K-Q of a non-trump suit | 20 × pairs (one unit per suit) |
| `Pinochle` / `Double Pinochle` | Q♠ + J♦ | 40 / 300 |
| `100 Aces` / `1000 Aces` | an Ace of each suit | 100 / 1000 |
| `80 Kings` / `800 Kings` | a King of each suit | 80 / 800 |
| `60 Queens` / `600 Queens` | a Queen of each suit | 60 / 600 |
| `40 Jacks` / `400 Jacks` | a Jack of each suit | 40 / 400 |
| `Trump Nine` | each 9 of trump | 10 × count |

A card may count in several categories but not twice in one. So run + a spare
trump K-Q = 190. Each unit carries the physical cards that form it.
`total_meld` sums units. `cards_in_meld(cards, trump)` returns the cards to lay
face-up, each physical card once (take, per (rank, suit), the maximum count
any category needs).

- The meld is exposed to everyone (`MeldExposed` per player: cards, units,
  total). With a human at the table this is the `MELD_EXPOSED` hold (§3.10);
  releasing it (or, at an all-computer table, the auction winner's
  `begin_play`) starts play with the auction winner leading. `begin_play` is
  refused with `WrongPhaseError` while the hold stands; the auction winner's
  own Play button releases the hold instead.
- **Toss in:** during `MELDING` only the auction winner may concede. It ends
  the meld hold and scores the round immediately (no tricks).

### 3.8 Trick play

- Auction winner leads trick 1; play is clockwise; 12 tricks.
- `Hand.legal_plays(trick, trump)` — the single implementation of:
  1. If you hold the led suit you must follow, but need not beat — unless
     trump was led, when you must beat the highest trump if you can.
  2. Else, if you hold trump you must trump; and if trump has been played and
     you can beat the highest trump, you must.
  3. Else any card.
- Winner: highest trump, else highest card of the led suit. Of two identical
  highest cards, the first played wins.
- A completed trick is *not* cleared by the fourth `play_card`: `Round` records
  a pending winner and refuses every `play_card` with `WrongPhaseError` until
  `clear_trick()` runs (scheduled by the service after
  `PINOCHLE_TRICK_CLEAR_SECONDS`). Trick winner leads next.

### 3.9 Scoring

- Card points: A 10, 10 10, K 5, Q 5, J 0, 9 0 (240 total); last trick +10
  (`LAST_TRICK_BONUS`).
- Team round total = recorded meld + card points + last-trick bonus.
- Bidding team: total ≥ contract → add total; else **set**: subtract
  `contract + their meld` (bid 300, meld 90, finish 260 → −390).
- Other team: add meld + trick points, **unless their trick points are zero**,
  then 0 (meld lost).
- Toss-in (`resolve_toss_in`): bidding team −contract; other team +meld only.
- Scores can go negative. Game ends at the end of a round when a team is
  ≥ 2000 (`WINNING_SCORE`); if both, the bidding team of that round wins.
- `RoundScored` carries, per team, `TeamRoundScore(team_id, meld, card_points,
  last_trick_bonus, round_total, points_applied, cumulative_score)` plus
  `round_number, bid_team_id, bid_winner_player_id, contract, made_contract,
  tossed_in`. Then `GameOver(winning_team_id, ns_score, ew_score)` if the game
  ended — but only after the `ROUND_SCORED` hold is released.

### 3.10 Pauses and holds

Two kinds of pause, both owned by the server and both states the game is in
(actions that would advance past them are rejected as out of phase):

- **Timed pauses** end by themselves: the trick clear
  (`TrickCompleted` … `TrickCleared`, default 1.5 s) and a computer's move delay
  (`SeatThinking` … its action, default 1.0 s).
- **Holds** wait, with no timeout, until *any one* seated player releases them:

| `HoldReason` | Begun after | Releasing it (`_resume_from`) |
| --- | --- | --- |
| `DRAW_TIED` | `DrawTied` | lays out a fresh spread (`DealerSelectionStarted`) |
| `DEALER_SELECTED` | `DealerSelected` | deals round 1 |
| `ROUND_ABANDONED` | all-four-pass `RoundAbandoned` | rotates dealer, deals |
| `MELD_EXPOSED` | the four `MeldExposed` | `begin_play` for the auction winner, `PlayBegun` |
| `ROUND_SCORED` | `RoundScored` | deals next round, or emits `GameOver` |

Rules: a hold is begun only if the table has at least one seat of type HUMAN
(kind, not connection); otherwise the service immediately does what the
release would. Computers never release holds and never act while one stands.
`acknowledge(hold_id)` naming a hold that is no longer current succeeds and
does nothing (idempotent); an unknown player id is `IllegalActionError`.
`Hold` is a frozen dataclass `(id, reason, seconds=None, ackable=False)` whose
`__post_init__` requires exactly one of `ackable` or `seconds`; factory
methods `timed` and `awaiting_release`. `HoldReason` also defines
`TRICK_CLEAR` and `THINKING` (unused by the server; the client uses the
lowercase names). Hold ids are per-game, incrementing.
`Game.begin_hold(reason, seconds=None, ackable=True)` stores it and emits
`HoldBegun`; `Game.end_hold(id)` emits `HoldEnded` and returns the hold only
if the id is current, else returns `None`.

Seating a computer in the last human seat ends any hold in force at once (by
calling the same `_resume_from`).

---

## 4. Domain layer (`pinochle/domain/`)

- `Suit` enum `SPADES, HEARTS, DIAMONDS, CLUBS` (iteration order matters for
  tie-breaks) with `glyph`, `character` (`S H D C`).
- `Rank` enum in Pinochle order with `.value` increasing; `short_name`
  (`9 J Q K T A`).
- `Card(rank, suit)` frozen/equal by value. `Deck` (48 cards, `shuffle(rng)`,
  `deal(count)`). `Hand` (`add`, `remove`, `remove_many`, `cards_of_suit`,
  `has_suit`, `legal_plays`). `Trick` (`play`, `lead_suit`, `is_complete`,
  `cards`, `plays: list[TrickPlay(player_id, card)]`, `winner()`, needs trump).
- `Player(player_id, name, position, type)`; `Team(team_id, name)` with
  `NS_TEAM_ID = "NS"`, `EW_TEAM_ID = "EW"`.
- `errors.py`: `PinochleError` ⊃ `UnknownGameError, NotYourTurnError,
  WrongPhaseError, IllegalActionError, SetupError`. Messages are
  human-readable and are shown to players verbatim (e.g. "It is p-south's turn
  to play.").
- `game.py`: `GamePhase` (`SETUP, DEALER_SELECTION, IN_ROUND, FINISHED`), the
  `Game` aggregate (game_id, teams, players in seat order, dealer, round number,
  current `Round`, current `Hold`, winning score, pending event list with
  `emit` / `pop_events`), and these dataclass events (each has `game_id`):

```
GameConfigured(players, teams, winning_score)   DealerSelectionStarted(spread_size)
DrawMade(player_id, position, card)             DrawTied(cards: dict[player_id, Card])
DealerSelected(dealer_player_id)                RoundStarted(round_number, dealer_player_id)
CardsDealt(player_id, cards)                    BidPlaced(player_id, amount|None, current_high)
ContractOffered(player_id, amount)              RoundAbandoned(declined_by|None)
TrumpNamed(suit)                                CardsPassed(from_player_id, to_player_id, cards)
MeldExposed(player_id, cards, units, total)     PlayBegun(leader_player_id)
ContractTossedIn(player_id)                     SeatReplaced(player_id, name, type)
SeatThinking(player_id)                         CardPlayed(player_id, card)
TrickCompleted(winner_player_id, plays)         TrickCleared(winner_player_id, next_leader_player_id|None)
RoundScored(...)                                TurnPrompt(player_id, phase, options: dict)
GameOver(winning_team_id, ns_score, ew_score)   HoldBegun(hold_id, reason, seconds, ackable)
HoldEnded(hold_id, reason)
```

Game operations: `add_team`, `add_player`, `start_dealer_selection`,
`set_dealer`, `next_dealer`, `rotate_dealer`, `begin_round`, `add_score`,
`seat_computer` (emits `SeatReplaced`; refused for a computer seat or a
finished game), `set_finished`, `begin_hold`, `end_hold`, plus read
properties.

---

## 5. Application layer

### 5.1 Ports

| Port | Methods |
| --- | --- |
| `AdminPort` | `create_game() -> id`, `add_player(game_id, player)`, `assign_teams(game_id, ns, ew)`, `start_game(game_id)`, `seat_computer(game_id, player_id)`, `abandon_game(game_id)` |
| `PlayerActionPort` | `draw_for_deal(g, p, position) -> Card`, `place_bid(g, p, amount\|None)`, `confirm_contract(g, p, accept)`, `name_trump(g, p, suit)`, `pass_cards(g, p, cards)`, `begin_play(g, p)`, `toss_in(g, p)`, `play_card(g, p, card)`, `acknowledge(g, p, hold_id)` |
| `GameStatePort` | `save(game)`, `load(game_id)` (raises `UnknownGameError`), `delete(game_id)` |
| `NotificationPort` | `notify(player_id, event)`, `broadcast(game_id, event)` |
| `SchedulerPort` | `call_later(delay_seconds, callback)` |
| `SeatTokenPort` | `mint(game_id, player_id) -> token`, `resolve(game_id, token) -> player_id\|None`, `revoke_seat`, `revoke_game` |
| `CardImagePort` | `get_image_path(card, fmt="svg")`, `get_back_path(fmt="svg", name=None)` |

### 5.2 `Round` (`services/round.py`)

The per-round state machine with phases `DEALING, BIDDING, CONFIRMING, TRUMP,
PASSING, MELDING, PLAYING, SCORING, ABANDONED`. Methods: `deal(rng)`,
`place_bid`, `confirm_contract`, `name_trump`, `partner_of`, `pass_cards`,
`begin_play`, `toss_in`, `play_card -> winner|None`, `clear_trick -> next
leader`, `legal_plays(player_id)`, `hand`, `meld`, `meld_total`, `meld_cards`,
`all_meld`; properties `current_player` (answers in every phase that has a
turn, including `MELDING` = auction winner), `tricks`, `trump`, `bid_winner`,
`trick_pending`, `current_trick_cards`, `current_trick_plays`, `tossed_in`,
`contract`, `current_high_bid`, `bid_history`.

### 5.3 `GameService` (implements `AdminPort` and `PlayerActionPort`)

Constructor: `(state, notifier, scheduler, rng=None, trick_clear_seconds=1.5)`.
Every operation runs one cycle, `_load_save`:

```
load Game → apply operation → append TurnPrompt for whoever is now on the clock
          → dispatch every pending event → save Game
```

- `_recipients(event)` is the *only* place privacy is decided: `CardsDealt` and
  `TurnPrompt` → that one player (`notify`); `CardsPassed` → the two partners;
  everything else → `broadcast`.
- `TurnPrompt` options by phase (regenerated after each operation that leaves a
  seat on the clock during a round; none in dealer selection):
  `BIDDING {minimum_bid, may_pass: true}`, `CONFIRMING {amount}`, `TRUMP {}`,
  `PASSING {count: 4}`, `MELDING {may_begin_play: true, may_toss_in: true}`,
  `PLAYING {legal_plays: [...]}` (from `Round.legal_plays`).
- `start_game` requires four players and two teams (`SetupError`), emits
  `GameConfigured` then `DealerSelectionStarted` (with a new spread).
- `play_card` schedules `_clear_trick` via the scheduler *after* saving. That
  callback runs its own cycle: `Round.clear_trick`, emit `TrickCleared`, and
  after trick 12 score the round.
- Holds are begun at the five points in §3.10 when `_has_human_seat(game)`.
  `acknowledge` → `game.end_hold(id)`; if something ended, `_resume_from(hold)`.
- `note_seat_thinking(game_id, player_id)` publishes `SeatThinking` without
  the turn-prompt step.
- `abandon_game` marks the game finished.

### 5.4 `SeatView` and `ComputerDriver`

`SeatView` is a frozen dataclass of what one seat may see: player id, partner
id, own hand, bid history, current high bid, trump, current trick cards, every
exposed meld, legal plays. The strategy only ever receives `SeatView` fields.

`ComputerDriver(service, state, scheduler, strategy, delay_seconds=1.0)` is
**both** a `PlayerActionPort` decorator (every method delegates to the service;
the web layer is handed the driver as `actions`) **and** a `NotificationPort`
observer appended to the composite notifier. After *every* event it runs:

```
pump(game):
    if a hold is in force: return
    if DEALER_SELECTION: for each undrawn computer seat, clockwise: schedule(seat); return
    seat = current round's current_player
    if seat is a computer: schedule(seat)

schedule(seat):
    if (game, seat) already pending: return      # coalesce (one cycle emits many events)
    mark pending; service.note_seat_thinking(game, seat)
    scheduler.call_later(delay, lambda: _act(game, seat))

_act: clear pending mark; reload game; if the seat is no longer on the clock
      (or has already drawn), do nothing; build SeatView; ask strategy; call the
      same service method a human POST reaches.
```

Deferral is mandatory: dispatch happens before save, so a synchronous `_act`
would load stale state. `AsyncioScheduler` defers even at delay 0.

### 5.5 `ComputerPlayerStrategy` (`strategies/`)

Constructor `(rng=None)`; the rng is used only for the draw.

- **Draw:** random untaken position.
- **Bid:** `estimate = 180 + max over suits of (total_meld(hand, suit) + 15 ×
  aces of that suit + 10 × max(0, cards of that suit − 4))`. Candidate = 250
  if no high bid else high + 10. Pass if candidate > estimate. Also pass when
  *yielding to partner*: both opponents have passed, partner is still in, and
  this seat has made fewer actual bids than its partner — unless it holds a
  whole run (A-10-K-Q-J of one suit), in which case it may make exactly one
  bid counted from the moment the second opponent passed.
- **Lone contract:** always accept. **Meld:** always begin play, never toss in.
- **Trump:** suit with most cards (ties by `Suit` order).
- **Play:** highest-ranked legal card.
- **Pass** (`choose_cards_to_pass(hand, trump, count=4, keep_trump=False)`):
  compute *protected* non-trump cards (one K and Q per marriage suit, one Q♠ and
  J♦ for a pinochle, one of each suit for any complete arounds). Order: all
  trump highest first, then unprotected aces, then unprotected others lowest
  first; take `count`. If short, add protected cards lowest first, then
  (for `keep_trump`) trump lowest first. The partner passes with
  `keep_trump=False`; the auction winner passing back uses `keep_trump=True`.

---

## 6. Driven adapters

| Adapter | Behaviour |
| --- | --- |
| `InMemoryGameState` | dict of live `Game` objects, no copying |
| `SseNotification` | the hub, §7.3 |
| `LoggingNotification` | logger `pinochle.events`: `event.published game_id=… recipient=… event=…` (`*` for broadcast); `CardsDealt`/`CardsPassed` redacted to counts; never logs tokens |
| `CompositeNotification(list)` | forwards each call to each notifier in order; `append()` |
| `PrintNotification` | prints events (headless wiring only) |
| `AsyncioScheduler` | `loop.call_later`; delay ≤ 0 → `loop.call_soon` |
| `FakeScheduler` | virtual clock; `advance(seconds)` runs only callbacks already pending and due now; anything they schedule waits for the next `advance` |
| `ImmediateScheduler` | runs callback synchronously (headless only; unsafe with the driver) |
| `InMemorySeatTokens(factory=lambda: secrets.token_urlsafe(32))` | per-game token → player id |
| `SvgCardImage(default_back="blue")` | resolves artwork paths; `FileNotFoundError` if missing; unknown format → `ValueError` |

---

## 7. Web layer (`pinochle/web/`)

### 7.1 Composition (`container.py`)

`Settings.from_env()` loads `.env` via python-dotenv without overriding the real
environment, then reads the variables in §10. Invalid seat type or a card back
that is not a plain bundled name → raise at startup. `TableDefaults` /
`SeatDefault` hold the setup form's defaults (North/East/West computer, South
human; names "North"… ; teams "North-South", "East-West").

```python
state     = InMemoryGameState()
tokens    = InMemorySeatTokens()
scheduler = scheduler or AsyncioScheduler()
sse       = SseNotification(queue_maxsize=settings.sse_queue_maxsize)
notifier  = CompositeNotification([sse, LoggingNotification()])
rng       = Random(settings.shuffle_seed) if settings.shuffle_seed is not None else None
service   = GameService(state, notifier, scheduler, rng=rng, trick_clear_seconds=settings.trick_clear_seconds)
driver    = ComputerDriver(service, state, scheduler, ComputerPlayerStrategy(rng=rng),
                           delay_seconds=settings.computer_delay_seconds)
notifier.append(driver)
cards     = SvgCardImage(default_back=settings.card_back)
```

`Container` exposes `admin` (service), `actions` (driver), `state`, `sse`,
`notifier`, `tokens`, `scheduler`, `cards`, `settings`. `create_app(container=None)`
in `main.py` builds the FastAPI app; module-level `app = create_app()` is what
uvicorn loads. The lifespan configures logging at `PINOCHLE_LOG_LEVEL`, logs
which `.env` was read, and logs a generated admin token as a WARNING.

### 7.2 HTTP API

Wire formats: card = two chars, rank `9 J Q K T A` + suit `S H D C` (`"TS"` =
ten of spades); suit = `"SPADES"|"HEARTS"|"DIAMONDS"|"CLUBS"`; seat =
`"NORTH"|"EAST"|"SOUTH"|"WEST"`. `card_codec.py` owns both directions.

Auth: player commands send `X-Seat-Token`; the seat stream takes `?t=` (EventSource
cannot set headers). A token resolves against the path's game id (other game →
403). Admin commands send `X-Admin-Token`, compared with
`secrets.compare_digest`; only the admin *stream* also accepts `?t=`. Refused
credentials log `action.rejected reason=… path=… method=…` on
`pinochle.security`.

**Admin** (`X-Admin-Token`):

| Method | Path | Effect |
| --- | --- | --- |
| GET | `/api/admin/defaults` | the table defaults for the setup form |
| POST | `/api/admin/games` | body `{"teams":{"ns":…,"ew":…},"seats":[{"seat","name","type":"human"\|"computer"}×4]}` → creates, assigns teams, adds players, mints a token per human seat. **201** `{"game_id", "seats":[{seat,name,type,player_id,join_url\|null}]}`; `join_url = {PUBLIC_BASE_URL}/join/{game_id}?t={token}`, returned only once |
| GET | `/api/admin/games/{id}` | seats with `joined` (computer, or human with an open stream) |
| POST | `/api/admin/games/{id}/start` | 409 `setup_incomplete` naming the first human seat without an open stream; else `start_game` |
| POST | `/api/admin/games/{id}/seats/{player_id}/unlink` | human only: revoke seat tokens, `sse.close_seat` |
| POST | `/api/admin/games/{id}/seats/{player_id}/computer` | human only: unlink, then `seat_computer` |
| POST | `/api/admin/games/{id}/abandon` | `{reason}` → finished, broadcast `game_abandoned`, revoke all tokens |
| GET | `/api/admin/games/{id}/stream` | admin SSE: `stream_started` (empty payload) then live broadcasts, no replay |

**Player** (`X-Seat-Token`, all return 204):

| Path | Body | Port method |
| --- | --- | --- |
| `POST /api/games/{id}/draw` | `{"position": 17}` | `draw_for_deal` (return value discarded) |
| `POST /api/games/{id}/bid` | `{"amount": 260}` or `{"amount": null}`/`{}` to pass | `place_bid` |
| `POST /api/games/{id}/contract` | `{"accept": true}` | `confirm_contract` |
| `POST /api/games/{id}/trump` | `{"suit": "HEARTS"}` | `name_trump` |
| `POST /api/games/{id}/pass` | `{"cards": ["AS","TS","KH","9C"]}` | `pass_cards` |
| `POST /api/games/{id}/begin-play` | — | `begin_play` |
| `POST /api/games/{id}/toss-in` | — | `toss_in` |
| `POST /api/games/{id}/play` | `{"card": "QS"}` | `play_card` |
| `POST /api/games/{id}/acknowledge` | `{"hold_id": 7}` | `acknowledge` |
| `GET /api/games/{id}/stream?t=…` | — | SSE, §7.3 |

**Pages and artwork:**

| Path | Serves |
| --- | --- |
| `GET /`, `GET /join/{game_id}` | `frontend/public/index.html` (`Cache-Control: no-cache`) |
| `GET /admin` | `admin.html`, server-side pre-filled with table defaults, and the token field filled when `?t=` is the valid admin token |
| `/assets/*` | `frontend/public/` (no-cache) |
| `/static/*` | `frontend/dist/` (no-cache) |
| `GET /cards/faces/{code}?fmt=svg\|png` | face; `Cache-Control: public, max-age=31536000, immutable` |
| `GET /cards/back?fmt=` | configured back, no-cache |
| `GET /cards/backs/{name}?fmt=` | named back, immutable |
| `GET /healthz` | `{"status":"ok"}` |

A missing page returns JSON 404 telling the operator to run `make build`.

**Errors** — every failure is `{"error": {"code", "message"}}`:

| Status | code | When |
| --- | --- | --- |
| 403 | `forbidden_seat` / `forbidden_admin` | bad/missing/revoked/wrong-game credential |
| 404 | `unknown_game` / `not_found` | no such game / missing artwork or page |
| 409 | `wrong_phase` | out of phase, incl. during the trick clear or `begin-play` under the meld hold |
| 409 | `not_your_turn` | wrong seat |
| 409 | `illegal_action` | illegal card/bid/pass, taken position, second draw, unknown player, admin action on computer seat |
| 409 | `setup_incomplete` | start before setup complete or before every human seat joined |
| 422 | `invalid_request` | malformed body, any `ValueError` (bad card/suit code, bad fmt, bad back name) |

### 7.3 SSE

**Hub** `SseNotification(queue_maxsize=256, history_maxlen=20000)`:
`subscribe(game, player) -> asyncio.Queue`, `unsubscribe`, `subscribe_admin`,
`unsubscribe_admin`, `close_seat(game, player) -> int` (puts a `STREAM_CLOSED`
sentinel on each of that seat's queues), `seats_connected(game) -> set`,
`history_since(game, player, after_seq) -> (frames, complete: bool)`,
`notify`, `broadcast`. Each dispatched event gets the next per-game sequence
number once, before fan-out; queues carry `(seq, event)`. A seat can have many
queues (several tabs; any may act). Broadcasts go to every seat and every admin
queue; `notify` only to that seat. History records recipient (`None` for
broadcast) and `history_since` returns only broadcasts plus that seat's own
frames. A full queue (`put_nowait` fails) is dropped from fan-out.

**Seat stream lifecycle:** resolve token (403 otherwise) → `subscribe` and then
`history_since(Last-Event-ID or 0)` with **no await in between** → if the seat
had no stream before, broadcast `seat_rejoined` → respond with headers
`Content-Type: text/event-stream`, `Cache-Control: no-cache, no-transform`,
`Connection: keep-alive`, `X-Accel-Buffering: no` → write `retry: 2000`, then
`stream_started` (seq 0, **no `id:` line**), then the replayed frames, then
live frames, writing `: keepalive` after `PINOCHLE_SSE_KEEPALIVE_SECONDS` idle.
On close: unsubscribe; if it was the seat's last stream, broadcast `seat_lost`.
Log `stream.opened` / `stream.closed` / `stream.replay_incomplete` /
`stream.bad_last_event_id` on `pinochle.stream`.

`stream_started` payload: `{"seat","player_id","you":{"name","type"},
"partial": bool, "resume": "fresh"|"resumed"|"incomplete"}` (`partial` true when
a round is in progress and the replay was not whole).

**Frame format** (`event_encoder.py`):

```
id: 42
event: card_played
data: {"seq":42,"type":"card_played","turn":{…},"payload":{"player_id":"p-west","card":"KS"}}

```

`turn` (from `turn_header.py`, read from the *live* game at encode time):
`{"phase", "current_player_id"|null, "paused": "trick_clear"|null,
"hold": {"id","reason","ackable"}|null, "round_number"}`. `phase` is the round
phase during a round, else the game phase. Hold reasons are serialized
lowercase (`meld_exposed`).

**Event payloads** (type names are snake_case of the event class; **P** =
broadcast, **S** = one seat, **T** = the two passing partners):

| event | vis | payload |
| --- | --- | --- |
| `game_configured` | P | `seats:[{player_id,name,type,seat}], teams:[{team_id,name}], winning_score` |
| `seat_replaced` | P | `{player_id,name,type}` |
| `dealer_selection_started` | P | `{spread_size:48, taken:[]}` |
| `draw_made` | P | `{player_id, position, card}` |
| `draw_tied` | P | `{cards:{player_id: card}}` |
| `dealer_selected` | P | `{dealer_player_id}` |
| `round_started` | P | `{round_number, dealer_player_id}` |
| `cards_dealt` | S | `{cards:[12 codes]}` |
| `turn_prompt` | S | `{phase, …options}` (§5.3, keys snake_case) |
| `bid_placed` | P | `{player_id, amount\|null, current_high}` |
| `contract_offered` | P | `{player_id, amount}` |
| `round_abandoned` | P | `{declined_by\|null}` |
| `trump_named` | P | `{suit}` |
| `cards_passed` | T | `{from_player_id, to_player_id, cards}` |
| `meld_exposed` | P | `{player_id, cards, units:[{name,points,cards}], total}` |
| `play_begun` | P | `{leader_player_id}` |
| `contract_tossed_in` | P | `{player_id}` |
| `seat_thinking` | P | `{player_id}` |
| `card_played` | P | `{player_id, card}` |
| `trick_completed` | P | `{winner_player_id, cards:[{player_id,card}]}` |
| `trick_cleared` | P | `{winner_player_id, next_leader_player_id\|null}` |
| `round_scored` | P | fields of §3.9, teams as a list of snake_case objects |
| `game_over` | P | `{winning_team_id, ns_score, ew_score}` |
| `hold_begun` | P | `{hold_id, reason, seconds, ackable}` |
| `hold_ended` | P | `{hold_id, reason}` |
| `seat_lost` / `seat_rejoined` | P | `{player_id}` — transport events (`transport_events.py`) |
| `game_abandoned` | P | `{reason}` — transport event |

---

## 8. Front end

### 8.1 Modules

- `types.ts` — the wire contract: `Frame {seq,type,turn,payload}`,
  `TurnHeader`, `FRAME_TYPES` (every event name).
- `stream.ts` — wraps `EventSource`, one listener per frame type; reports
  connection state `connecting | live | down | closed`.
- `token.ts` — seat: game id from `/join/{id}`, token from `?t=`, mirrored to
  `sessionStorage` keyed by game (not localStorage, so four tabs = four
  seats); the token is left in the URL. Admin: token from `/admin?t=` or the
  field, remembered in `sessionStorage`.
- `api.ts` (admin calls, `ApiError` with the server's code/message),
  `actions.ts` (player POSTs).
- **Pure, Node-testable modules** (no DOM): `state.ts`, `cards.ts`,
  `layout.ts`, `view.ts`, `notice.ts`, `deal.ts`.
- DOM modules: `main.ts` (entry), `table.ts` (renders the table), `hand.ts`,
  `spread.ts`, `panels.ts`, `sweep.ts`, `admin.ts`, `log.ts`.

### 8.2 State (`state.ts`)

`applyEvent(state, frame) -> GameState` is pure and never mutates its input.
It applies the type's handler, then refreshes `phase`, `currentPlayerId`,
`paused`, `hold` from the turn header, records `lastSeq = max(...)`, and drops a
prompt the header no longer agrees with. `paused: "trick_clear"` is folded into
`hold = {id: null, reason: "trick_clear", ackable: false}`.

`GameState` fields: `me`, `partial`, `seats[{playerId,name,type,seat,teamId}]`,
`teams[{teamId,name,score}]`, `winningScore`, `spreadId` (increments per
spread), `spreadSize`, `draws[{playerId,position,card}]`, `dealerPlayerId`,
`roundNumber`, `hand` (sorted), `handCounts`, `bids[{playerId,amount}]`,
`highBid`, `offer`, `contract {playerId,amount}`, `trump`, `received`, `sent`,
`meld: Record<playerId,{cards,units,total}>`, `teamMeld`, `leaderPlayerId`,
`trick[{playerId,card}]`, `trickWinnerPlayerId`, `lastTrick {plays,
winnerPlayerId}`, `tricksTaken` and `trickPoints` per team (card points only,
no bonus), `tossedInBy`, `thinkingPlayerId`, `prompt`, `phase`,
`currentPlayerId`, `paused`, `hold`, `roundSummary`, `gameOver`, `lastSeq`.
It never computes legality or trick winners. `seat_lost`, `seat_rejoined`,
`game_abandoned`, `hold_begun`, `hold_ended` are subscribed but change nothing.
`round_started` resets per-round fields. Pass-sent/received cards are removed
from/added to `hand`. `trick_cleared` moves the trick to `lastTrick` and adds
to the winner team's `tricksTaken`/`trickPoints`. `card_played` clears
`thinkingPlayerId`.

### 8.3 Hand order (`cards.ts`)

`sortHand(cards, trump=null)`: suits ♠♥♣♦ (black/red alternate), within a suit
A, T, K, Q, J, 9. Once trump is named, trump first and colours still
alternate, choosing the earlier suit in ♠♥♣♦ where either would do — the four
orders are exactly ♠♥♣♦, ♥♠♦♣, ♣♥♠♦, ♦♠♥♣. `faceUrl(code) =
/cards/faces/<code>`, `backUrl() = /cards/back`.

### 8.4 Table layout and rendering

- `#stage` is a fixed **1420 × 1000** px layout scaled to the window by
  `transform: scale(var(--stage-scale))` from the top-left, with negative
  margins so the scaled box is the drawn size; `main.ts` sets the scale on
  resize. Green felt (`--felt: #17603a`), dark page background. Team colours
  `--ns: #ffd479`, `--ew: #8fd6ff`. Own cards 148×208; other hands' backs at
  0.75×; small cards 92×130.
- `index.html` elements: `#stage > #felt (seat-top, seat-left, seat-right,
  #spread, #centre)`, `#scoreboard`, `#deal-flight`, `#contract-indicator`,
  `#trump-indicator`, `#notice`, `#toast`, `#connection`, and `#bottom-bar
  (seat-bottom, #status, #panel, #hand)`; loads `/static/main.js` as a module.
- `layout.placement`: own seat bottom, next clockwise seat **left**, partner
  top, previous seat right.
- Seats show name (+ " (dealer)"), team colour, italic for computer, trailing
  " …" while thinking, a highlight while acting, the drawn card face up during
  dealer selection, a fan of backs sized by `handCounts` (empty fan keeps its
  footprint; left/right fans vertical), the latest bid call during the
  auction, and meld grouped by unit on a panel edged in team colour while
  phase is `MELDING` (left/right seats stack meld in a column beside the hand).
- Own hand: fanned by rotation about a pivot below the hand
  (`layout.fanAngles(count)`: constant step derived from 30 % visible width,
  card aspect 74/104, pivot depth 2.4, capped at 60° total arc). When trump is
  named the re-sort is animated (FLIP-style) so cards do not teleport.
- Spread (FR-11c): `layout.scatter(count, random)` places the 48 backs once per
  `spreadId` on a jittered grid (jitter 0.62) over the inner felt, tilted up to
  ±24°, overlapping. A press that moves (beyond a small threshold) drags the
  card, which then stays where dropped and on top; a press that does not move
  draws it. Drawn cards leave the spread and appear face up at the drawer's
  seat.
- Trick area (`#centre`): each played card offset toward its player; the
  winning card is ringed while the trick clears. After `round_scored` the
  centre shows the round summary table (team, meld, cards, last trick, round
  total, applied, score; bidding team highlighted); after `game_over`, the
  final result.
- Trick stacks (UI-14c): each team's taken tricks as a face-down stack of
  back-size cards with the team's card-point total on it; for any viewer, the
  top seat's team's stack to the left of the top hand, the other team's below
  the left hand.
- Trick sweep (`sweep.ts`): on `trick_cleared`, the four cards gather into one
  pile (0–30 % of the flight), flip face down (to 55 %), then fly to the
  winning team's stack; 1000 ms total. Skipped under
  `prefers-reduced-motion`. Cosmetic only.
- Scoreboard: collapsible to one toggle; shows team scores (with this round's
  meld beside them), round number, contract and bidder, trump, score played to,
  each seat's meld (unit names until the first trick is gathered, then totals)
  and the bid history. Separate felt plaques show winning bid and trump.
- Status line (`view.statusLine`): "Drawing for the deal — pick a card.",
  "Dealing the cards…", "Waiting for the game to start…", or "Your turn —
  <phrase>" / "<Name>'s turn — <phrase>" with phrases `bidding`, `accept or
  decline the contract`, `name trump`, `pass four cards`, `meld`, `play a card`.
  A "last trick" toggle beside it shows the previous trick during the current
  one only.
- `render()` rebuilds the table from state each frame, except it does not
  rebuild under an active drag (hand card or spread card), and rebuilds the
  action panel and notice only when their content key changes (so a half-typed
  bid or a Continue button under the pointer survives).

### 8.5 Interaction

All actions go through one `attempt` wrapper that refuses to send unless the
stream is `live`, and shows a refused action's server message in `#toast`
that fades after 4 s.

- **Play:** legal cards (from `prompt.legal_plays`) are clickable and
  draggable onto the trick area — identical outcomes. Illegal cards dimmed and
  inert. No play during a pause.
- **Bid panel:** number field starting at `minimum_bid`, +10 and +50 buttons,
  Bid, Pass; refuse locally amounts below minimum or not multiples of 10.
- **Lone contract:** "Accept *n*" / "Decline".
- **Trump:** four suit buttons with glyphs.
- **Pass:** click or drag a card from the hand into the pass tray and back
  (selection by position, since duplicates exist); Confirm enabled at exactly
  four. Show sent/received cards to the passing team.
- **Meld panel** (auction winner): side's meld, how much more is needed in
  cards to make the contract, **Play** (releases the meld hold if one stands,
  else POSTs `begin-play`) and **Toss in**.
- **Draw:** click a spread card while this seat has not drawn.
- **UI-18:** every enabled control and drop target must actually receive
  clicks where it is drawn at every supported window size (nothing overlays
  it); the spread's overlap is the one exception.

### 8.6 Notices (`notice.ts`), connection, visible deal

`notice(state) -> {text, kind: "result"|"hold"|"final", key, release: holdId|null} | null`.
One sentence, replacing the last; no history; public; the client composes the
words (the server sends no display text).

- Game over → final: `"<Team name> team wins, <ns> to <ew>."`
- While a hold stands (Continue button inside the notice when `ackable`,
  calling `acknowledge(id)`):
  `trick_clear` → `"<Name> takes the trick."`;
  `thinking` → `"<Name> is thinking…"`;
  `draw_tied` → `"Tied for high card - select again."`;
  `dealer_selected` → `"<Name> deals."`;
  `round_abandoned` → `"Everyone passed"`;
  `meld_exposed` → `"Review the meld laid out on the table."`;
  `round_scored` → the round headline; unknown → `"The game is paused."`.
- Otherwise the newest concluded result: round headline
  `"Round <n>: <Name> made|went set on the <c> contract."` or
  `"Round <n>: <Name> tossed in the <c> contract."`; `"<Name> tossed the
  contract in."`; `"<Name> took the last trick."`; nothing while a trick is on
  the table before the first is taken; `"<Name> plays <c> in <glyph> <suit>."` or
  `"<Name> won the auction at <c>."`; `"<Name> bid <c> alone, and is deciding
  whether to take it."`; `"<Name> deals."`.

Connection: `down` or `closed` shows a persistent banner in `#connection`; a
partial replay marks the view partial.

Visible deal (`deal.ts`): on `cards_dealt`, show 16 packets of 3 (4 per seat),
150 ms apart (`DEAL_PACKET_MS`), clockwise from the dealer's left, flying from
the dealer; `dealingView(state, packetCount)` projects the state with no
prompt. Frames arriving meanwhile are queued and applied in order afterwards.
These presentational timers never affect the game.

### 8.7 Admin console (`admin.html`, `admin.ts`, `style.css`, `log.ts`)

- Token field (from `?t=` or server fill), remembered in `sessionStorage`. A
  `forbidden_admin` failure explains where the token comes from and that
  `/admin?t=<token>` fills it in.
- Setup form: two team names; per seat a name and human/computer; pre-filled
  (same defaults in the HTML as on the server — a test holds them equal), then
  refreshed from `/api/admin/defaults`.
- After Create: a seat board (seat, name, type, joined/waiting, join link with a
  Copy button, and for human seats **Seat computer** and **Unlink** behind
  confirmations), plus Start, Refresh, Abandon (with reason).
- Opens the admin stream and appends every frame to a raw log; `seat_lost`,
  `seat_rejoined`, `seat_replaced` refresh the seat board automatically.

---

## 9. Logging and security

Never log hands, passed cards or tokens. uvicorn runs with `--no-access-log`
(stream URLs carry tokens). Log levels configurable via
`PINOCHLE_LOG_LEVEL`.

---

## 10. Configuration (`PINOCHLE_*`, environment wins over `.env`)

| Variable | Default |
| --- | --- |
| `PINOCHLE_ADMIN_TOKEN` | generated per run (`secrets`), logged as a warning |
| `PINOCHLE_PUBLIC_BASE_URL` | `http://localhost:8000` |
| `PINOCHLE_TRICK_CLEAR_SECONDS` | `1.5` |
| `PINOCHLE_COMPUTER_DELAY_SECONDS` | `1.0` (0 = full speed) |
| `PINOCHLE_CARD_BACK` | `blue` (plain bundled name; a path is refused) |
| `PINOCHLE_TEAM_NS`, `PINOCHLE_TEAM_EW` | `North-South`, `East-West` |
| `PINOCHLE_SEAT_{NORTH,EAST,SOUTH,WEST}_NAME` | `North` … `West` |
| `PINOCHLE_SEAT_{…}_TYPE` | South `human`, others `computer`; other values refused |
| `PINOCHLE_LOG_LEVEL` | `INFO` |
| `PINOCHLE_SSE_KEEPALIVE_SECONDS` | `15` |
| `PINOCHLE_SSE_QUEUE_MAXSIZE` | `256` |
| `PINOCHLE_FRONTEND_DIR` | `frontend` |
| `PINOCHLE_SHUFFLE_SEED` | unset |
| `PINOCHLE_BIND_ADDRESS`, `PINOCHLE_PORT` | `127.0.0.1`, `8000` (compose only) |

`.env.example` documents every key.

---

## 11. Tooling and deployment

**Makefile** (with a `help` target that greps `## ` comments; `PYTHON` prefers
`.venv/bin/python`; `TSC ?= npx -y -p typescript@5 tsc`):
`test` (= `test-py` + `test-fe`), `test-py` (pytest), `test-fe` (`cd frontend
&& $(TSC) && node --test "test/*.test.js"`), `test-browser` (build, then
`scripts/hit_test.py`), `build`, `watch`, `dev` (build + `scripts/dev.sh`),
`dev-fast` (both delays 0), `seed`, `seed-watch` (`--humans none`), `seed-all`
(`--humans NORTH,EAST,SOUTH,WEST`), `record`, `docker`, `docker-logs`,
`docker-down`, `clean`.

**Scripts:**
- `dev.sh` — exports defaults (`PINOCHLE_ADMIN_TOKEN=dev`, etc.), prints the
  console link `…/admin?t=dev`, runs `uvicorn pinochle.web.main:app --reload
  --reload-dir pinochle --host 127.0.0.1 --port 8000 --workers 1`.
- `seed.py` — creates a game over HTTP (`--humans` list, default `SOUTH`),
  prints join links, polls until every human seat has joined, then starts it.
- `record_frames.py` — plays an all-computer game (`--rounds N`) through the
  real service and encoder on a fake scheduler and writes one seat's frames to
  `frontend/test/fixtures/seat-stream.json`.
- `hit_test.py` — serves `frontend/test/browser/reachability.html` and runs it
  in headless Chrome; the page replays the fixture through the real reducer,
  renderer and CSS and, after every frame, checks with `elementFromPoint` that
  each enabled control and drop target receives its own clicks at window
  sizes 1600x1100, 1200x900 and 900x700 (`--size WxH` repeatable).
- `seed.py` flags: `--humans`, `--base` (default `http://localhost:8000`),
  `--token` (default `dev`), `--no-start`. `record_frames.py` flags: `--seat`
  (default `p-south`), `--rounds`, `--seed` (default 7), `--out`.

**Docker:** two-stage `docker/Dockerfile` — `node:22-slim` compiles the client
with `npx -y -p typescript@5 tsc`; `python:3.12-slim` does `pip install .`,
copies `frontend/public` and the compiled `dist`, sets
`PINOCHLE_FRONTEND_DIR=/app/frontend`, runs as unprivileged user `pinochle`,
has a urllib `HEALTHCHECK` on `/healthz`, and
`CMD ["uvicorn","pinochle.web.main:app","--host","0.0.0.0","--port","8000","--workers","1","--timeout-keep-alive","75","--no-access-log"]`.
`.dockerignore` excludes `frontend/dist`, tests, docs, venvs. `docker/compose.yaml`:
one service `pinochle`, build context `..`, `restart: unless-stopped`,
`env_file: ../.env`, ports
`"${PINOCHLE_BIND_ADDRESS:-127.0.0.1}:${PINOCHLE_PORT:-8000}:8000"`.
Write `docs/docker-usage.md` covering running, a reverse proxy (no buffering
of `text/event-stream`, long read timeout, strip `t` from access logs), and
moving the image to another server.

---

## 12. Tests and build order

Build in this order, each step with its tests passing:

1. Domain: cards, deck, hand legality, trick winner, bidding, meld (every row
   of the table, doubles, run + spare royal marriage = 190, `cards_in_meld`
   dedup), scoring (made, set, zero-trick opponents, toss-in), hold invariants.
2. Error hierarchy; ports' ABC contracts (cannot instantiate, concrete
   subclass works).
3. Scheduler adapters (fake clock semantics), seat tokens.
4. `Round` and `GameService`: full event sequences, holds and idempotent
   release, all-computer tables skipping holds, event privacy (no seat ever
   receives another's `cards_dealt`/`turn_prompt`; opponents never receive
   `cards_passed`).
5. Notification adapters and the hub (fan-out, seq numbers, replay filtering,
   `close_seat`, overflow), the encoder and turn header.
6. Web layer: every router via `httpx.ASGITransport` against
   `create_app(container)` built with a `FakeScheduler` and a seeded RNG;
   status mapping; stream replay and resume modes; pages; table defaults.
7. Computer driver and strategy (pump, coalescing, re-validation, bidding
   valuation, yielding to partner, passing both directions). Milestone: an
   all-computer game runs to `game_over` over HTTP on the fake clock
   (`tests/web/test_end_to_end.py`).
8. Front end, then its Node tests: reducer, replay of the recorded fixture,
   hand order, layout, notices, view text, visible deal.
9. Docker, docs, README, CHANGELOG (Keep a Changelog format).

No test sleeps; every pause is advanced on `FakeScheduler`.

---

## 13. Acceptance

- `pip install -e . && make test` passes.
- `make dev`, open `http://localhost:8000/admin?t=dev`, create the default
  table, open South's join link in its own tab, Start: the spread appears,
  South draws, the dealer is announced with Continue, the hand is dealt three
  cards at a time, bidding, trump, pass, meld hold, twelve tricks with
  computers moving after a visible "…" delay, the trick sweeping to the
  winner's stack, the round summary held with Continue, and rounds continue
  until a team reaches 2000.
- `make seed-watch` runs an all-computer game to completion with no holds;
  the console's log shows every public frame.
- Closing and reopening a seat's tab replays the game to the same table; a
  second tab for the same seat works alongside the first.
- Seat computer on a disconnected human seat resumes play from where it
  stopped.
