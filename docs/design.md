# Pinochle — Design

**Status:** Describes the code as of version 1.3.0
**Last updated:** 2026-09-24
**Implements:** `docs/requirements.md`

---

## 1. Purpose and scope

`docs/requirements.md` says *what* the system does. This document says *how*
it is built. Sections cite the requirement identifiers they satisfy, so the
two documents can be read side by side. Source files cite sections of this
document by number (`design.md §6.4`), so the numbering is kept stable.

It covers:

- the design principles and the dependency rule (§2);
- the split between the Python server and the TypeScript front end (§3);
- the server's internal structure as a ports-and-adapters application (§4);
- the HTTP surface (§5) and the Server-Sent Events stream (§6);
- how computer players are driven (§7);
- the browser client and the administrator's console (§8);
- the administrator's workflow (§9);
- packaging and configuration (§10);
- testing, dependencies, and tooling (§11–§13);
- design decisions (§14) and known limitations (§15).

---

## 2. Design principles

### 2.1 The dependency rule

```
╔══════════════════════════════════════════════════════════════════════════╗
║  DRIVING SIDE (INBOUND)                                                  ║
║                                                                          ║
║   Player table (frontend/src/main.ts)   Admin console (admin.ts)         ║
║        │ HTTP POST + SSE GET                  │ HTTP + SSE GET           ║
║        ▼                                      ▼                          ║
║   ┌──────────────────────────────────────────────────────────┐           ║
║   │  pinochle/web/ — FastAPI driving adapter                 │           ║
║   │  routers: admin · player · stream · cards                │           ║
║   │  (no game logic; translates HTTP ⇄ ports, events → SSE)  │           ║
║   └──────────────────────────────────────────────────────────┘           ║
╚══════════════════════════════│═══════════════════════════════════════════╝
                               │ calls
                               ▼
╔══════════════════════════════════════════════════════════════════════════╗
║  APPLICATION LAYER  (pinochle/services/, pinochle/strategies/)           ║
║                                                                          ║
║   GameService     implements AdminPort + PlayerActionPort                ║
║   ComputerDriver  decorates PlayerActionPort; observes NotificationPort  ║
║   Round           the per-round state machine                            ║
║   SeatView        what one seat may see (FR-74)                          ║
║   ComputerPlayerStrategy                                                 ║
║                                                                          ║
║   Ports (pinochle/ports/, one ABC per module):                           ║
║     driving: AdminPort · PlayerActionPort                                ║
║     driven:  GameStatePort · NotificationPort · SchedulerPort ·          ║
║              SeatTokenPort · CardImagePort                               ║
╚══════════════════════════════│═══════════════════════════════════════════╝
                               │ implemented by
                               ▼
╔══════════════════════════════════════════════════════════════════════════╗
║  DRIVEN SIDE (OUTBOUND ADAPTERS)  (pinochle/adapters/)                   ║
║                                                                          ║
║   InMemoryGameState      → GameStatePort                                 ║
║   SseNotification        → NotificationPort  (per-seat queues + replay)  ║
║   LoggingNotification    → NotificationPort  (NFR-9 audit log)           ║
║   CompositeNotification  → NotificationPort  (tees to the others)        ║
║   PrintNotification      → NotificationPort  (headless wiring only)      ║
║   AsyncioScheduler       → SchedulerPort     (production)                ║
║   FakeScheduler          → SchedulerPort     (tests, virtual clock)      ║
║   ImmediateScheduler     → SchedulerPort     (headless wiring only)      ║
║   InMemorySeatTokens     → SeatTokenPort                                 ║
║   SvgCardImage           → CardImagePort     (pinochle/card_images/)     ║
╚══════════════════════════════│═══════════════════════════════════════════╝
                               │ uses
                               ▼
╔══════════════════════════════════════════════════════════════════════════╗
║  DOMAIN LAYER  (pinochle/domain/ — pure; no I/O, no frameworks)          ║
║                                                                          ║
║   Card · Rank · Suit · Deck · Hand · Trick · TrickPlay                   ║
║   Player · PlayerType · Position · Team · TeamRoundScore                 ║
║   BiddingRound · BidEntry · MeldUnit · detect_meld · scoring functions   ║
║   Hold · HoldReason · PinochleError hierarchy                            ║
║   Game (aggregate root, GamePhase, and every domain event)               ║
╚══════════════════════════════════════════════════════════════════════════╝
```

**Data flow:** browser gesture → `POST /api/games/{id}/…` with `X-Seat-Token` →
the web router resolves the token to a player id and decodes the body → the
`PlayerActionPort` method on `ComputerDriver` → delegated to `GameService` →
`GameService` loads the `Game`, runs the domain operation through `Round`,
appends the acting seat's `TurnPrompt`, and dispatches the pending events →
`CompositeNotification` hands each one to the SSE hub, the audit log, and the
computer driver → the hub numbers it, records it for replay, and places it on
every queue the recipient list permits → each stream generator encodes it as
an SSE frame with the current turn header → the client folds the frame into
its state and redraws. The POST itself answers `204 No Content` (RT-2).

**Dependency rule:** the application layer (`pinochle/services/`,
`pinochle/strategies/`) imports from `pinochle/domain/` and `pinochle/ports/`
and nothing else. It does not import FastAPI, Starlette, `asyncio`, `time`,
`json`, or any module under `pinochle/adapters/` or `pinochle/web/` (ARC-1,
ARC-9).

### 2.2 The client renders; it never decides

ARC-2 and RT-8 are enforced by three habits:

1. Every command endpoint returns `204`. The client learns the outcome only when
   the corresponding event arrives on its stream.
2. The client holds no timer that affects the game. Every pause — the trick
   clear, a computer's delay, and every hold — is owned by the server and
   delimited by events (RT-10). The client's only timers are presentational
   (§8.6).
3. The client is *told* what is legal. The acting seat receives a private
   `turn_prompt` carrying the legal plays, the minimum bid, or whatever that
   phase offers (§6.5), and every frame carries a public turn header saying
   whose turn it is and what the game is paused on (§6.4).

---

## 3. Repository layout

The server and the front end are separate top-level trees. Nothing under
`frontend/` is imported by Python, and nothing under `pinochle/` is compiled by
`tsc`. The runtime contract between them is the HTTP + SSE surface of §5 and
§6. The one browser-facing asset inside the Python package is the card
artwork, which the server serves through `CardImagePort` (UI-16, ARC-8).

```
$PROJECT_ROOT/
├── pinochle/                     # SERVER — the Python package
│   ├── domain/                   # pure game logic (cards/ subpackage for Card, Rank, Suit, Deck)
│   ├── ports/                    # ABCs, one per module
│   ├── services/                 # application layer: GameService, Round, ComputerDriver, SeatView
│   ├── strategies/               # ComputerPlayerStrategy
│   ├── adapters/                 # driven adapters
│   ├── web/                      # FastAPI driving adapter
│   │   └── routers/              # admin, player, stream, cards
│   ├── card_images/              # artwork: fronts/, backs/, each with png_96_dpi/
│   └── app.py                    # headless wiring (create_default_app)
│
├── frontend/                     # FRONT END — everything the browser runs
│   ├── package.json              # devDependency: typescript only
│   ├── tsconfig.json
│   ├── public/                   # hand-written, served at /assets/
│   │   ├── index.html            # the player's table
│   │   ├── admin.html            # the administrator's console
│   │   ├── table.css             # the table's stylesheet
│   │   └── style.css             # the console's stylesheet
│   ├── src/                      # TypeScript sources (§8.1)
│   ├── dist/                     # tsc output, served at /static/ — git-ignored
│   └── test/                     # node --test suites, fixtures, browser harness
│
├── tests/                        # server tests (pytest), mirrors pinochle/
├── scripts/                      # dev.sh, seed.py, record_frames.py, hit_test.py
├── docker/                       # Dockerfile, compose.yaml
├── docs/                         # requirements, design, impl, docker-usage
├── Makefile
├── .env.example
└── pyproject.toml
```

---

## 4. Server design

### 4.1 Domain layer

`pinochle/domain/` holds the rules and the aggregate:

| Module | Contents |
| --- | --- |
| `cards/card.py`, `rank.py`, `suit.py`, `deck.py` | `Card` (equal by rank and suit, so the two copies are interchangeable — FR-19), `Rank` in Pinochle order (FR-18), `Suit`, and the 48-card `Deck` with a seedable `shuffle(rng)` (NFR-7). |
| `hand.py` | `Hand`, including `legal_plays(trick, trump)`, the single implementation of FR-53's follow-and-beat, trump-and-overtrump rule. |
| `trick.py` | `Trick` and `TrickPlay`; `winner()` implements FR-54 and, by keeping the first of two identical cards, FR-55. |
| `bid.py` | `BiddingRound` and `BidEntry`, `MINIMUM_BID = 250`, `BID_INCREMENT = 10`. The auction ends when one bidder remains after a bid, or when all four have passed (FR-24–FR-31). |
| `meld.py` | `MeldUnit`, `detect_meld(cards, trump)` (FR-47–FR-49), `total_meld`, and `cards_in_meld`, which returns the physical cards to lay face up, each once (FR-44). |
| `scoring.py` | Card values, `LAST_TRICK_BONUS`, `WINNING_SCORE = 2000`, `score_card_points`, `resolve_round` (FR-62–FR-64) and `resolve_toss_in` (FR-50c). |
| `player.py` | `Player`, `PlayerType`, `Position`. `Position.team_id` derives the partnership, so FR-4a holds by construction. |
| `team.py` | `Team` and the fixed ids `NS_TEAM_ID`, `EW_TEAM_ID`. |
| `team_round_score.py` | `TeamRoundScore`, one team's line of FR-66 arithmetic. |
| `hold.py` | `Hold` and `HoldReason` (RT-13). A `Hold` is either timed or awaiting release, never both; `__post_init__` enforces it. |
| `errors.py` | The `PinochleError` hierarchy (§4.8). |
| `game.py` | The `Game` aggregate, `GamePhase`, and every domain event. |

`Game` stores the long-lived state — teams, players in seat order, dealer,
round number, the current `Round`, the current `Hold` — and an event list that
the service drains after each operation. Its operations are setup
(`add_team`, `add_player`, `start_dealer_selection`), dealer bookkeeping
(`set_dealer`, `rotate_dealer`), `begin_round`, `add_score`, `seat_computer`
(which emits `SeatReplaced`), `set_finished`, and the hold pair:

- `begin_hold(reason, seconds=…, ackable=…)` assigns the next per-game hold id,
  stores the hold, and emits `HoldBegun`;
- `end_hold(hold_id)` clears the hold and emits `HoldEnded` only if the id
  names the hold in force, and otherwise returns `None` and emits nothing —
  which is what makes a release idempotent (RT-13).

`GamePhase` is `SETUP → DEALER_SELECTION → IN_ROUND → FINISHED`. The finer
round phases live on `Round` (§4.3).

### 4.2 Ports

| Port | Kind | Methods |
| --- | --- | --- |
| `AdminPort` | driving | `create_game`, `add_player`, `assign_teams`, `start_game`, `seat_computer`, `abandon_game` |
| `PlayerActionPort` | driving | `draw_for_deal`, `place_bid`, `confirm_contract`, `name_trump`, `pass_cards`, `begin_play`, `toss_in`, `play_card`, `acknowledge` |
| `GameStatePort` | driven | `save`, `load` (raises `UnknownGameError`), `delete` |
| `NotificationPort` | driven | `notify(player_id, event)`, `broadcast(game_id, event)` |
| `SchedulerPort` | driven | `call_later(delay_seconds, callback)` |
| `SeatTokenPort` | driven | `mint`, `resolve`, `revoke_seat`, `revoke_game` |
| `CardImagePort` | driven | `get_image_path(card, fmt)`, `get_back_path(fmt, name)` |

Token generation sits behind a port for the same reason shuffling takes an
`rng`: tests need it deterministic, production needs it unguessable.

### 4.3 Application layer

**`Round`** (`pinochle/services/round.py`) is the per-round state machine:

```
DEALING → BIDDING → [CONFIRMING] → TRUMP → PASSING → MELDING → PLAYING → SCORING
                  ↘ ABANDONED    ↘ ABANDONED                  ↘ SCORING (toss-in)
```

It deals three at a time from the dealer's left (FR-21), runs the
`BiddingRound`, enforces that only the bid winner names trump, orders the pass
(partner first, FR-42), captures every player's meld once both passes are in
(FR-46), and plays tricks. A completed trick is not cleared by `play_card`:
it sets a pending winner, and `play_card` refuses with `WrongPhaseError`
until `clear_trick()` runs — that is RT-9's "the next leader cannot play into
the last trick". `current_player` answers whose turn it is in every phase that
has one, including `MELDING`, where it is the auction winner.

**`GameService`** implements both driving ports. Every operation follows one
cycle in `_load_save`:

```
load Game → apply the operation → append TurnPrompt for whoever is on the clock
          → dispatch every pending event → save Game
```

- `_recipients(event)` is the single place event privacy is decided (RT-1,
  NFR-6): `CardsDealt` and `TurnPrompt` go to one seat, `CardsPassed` to the
  two partners, everything else is broadcast.
- The dealer-selection spread (`_DealerSpread`: 48 cards and who drew which
  position) is transient application state held by the service, not the
  aggregate. Its absence is the phase check for `draw_for_deal` (FR-11a).
- `play_card` schedules `_clear_trick` through `SchedulerPort` *after* the
  save, so the callback's own cycle never nests inside the one that scheduled
  it. `_clear_trick` emits `TrickCleared` and, after the twelfth trick, scores
  the round.
- Holds (§6.7) are begun at five points — a tied draw, a settled dealer, an
  all-pass throw-in, the exposed meld, a scored round — but only when
  `_has_human_seat(game)`; an all-computer table goes straight on.
  `acknowledge` releases the named hold and calls `_resume_from`, which does
  whatever the hold was standing in front of. `_release_unattended_hold`
  reuses `_resume_from` when `seat_computer` removes the last human seat
  (RT-12a).
- `note_seat_thinking` publishes `SeatThinking` without the turn-prompt step,
  because the seat on the clock has not changed.
- The constructor takes an optional `Random` (NFR-7) and
  `trick_clear_seconds` (UI-15).

**`ComputerDriver`** drives the computer seats (§7).

**`SeatView`** is the frozen slice of a round one seat may see (FR-74).

### 4.4 Driven adapters

| Adapter | Port | Notes |
| --- | --- | --- |
| `InMemoryGameState` | `GameStatePort` | A dict of live `Game` objects; no copying, so every caller shares one reference per game. NFR-8: a restart loses the game. |
| `SseNotification` | `NotificationPort` | The hub: per-seat and admin subscriber queues, a per-game sequence number, and a bounded per-game replay history. Deals in `GameEvent` objects; serialisation is the web layer's job. See §6.3. |
| `LoggingNotification` | `NotificationPort` | NFR-9: one `event.published` record per delivery on the `pinochle.events` logger, with game id and recipient (`*` for broadcast). `CardsDealt` and `CardsPassed` are redacted to counts. |
| `CompositeNotification` | `NotificationPort` | Forwards each call to a list of notifiers, in order, so the service depends on one port. |
| `PrintNotification` | `NotificationPort` | Prints events; used only by `create_default_app`. |
| `AsyncioScheduler` | `SchedulerPort` | `loop.call_later`; a delay of `0` or less becomes `loop.call_soon`, which still defers to a later tick (§7.2). |
| `FakeScheduler` | `SchedulerPort` | Virtual clock for tests. `advance(seconds)` runs only callbacks already pending and now due; anything they schedule waits for the next `advance` (ARC-10). |
| `ImmediateScheduler` | `SchedulerPort` | Runs the callback synchronously. Used only by `create_default_app`; unsafe with the computer driver, which must not re-enter a cycle in progress. |
| `InMemorySeatTokens` | `SeatTokenPort` | `secrets.token_urlsafe(32)` by default, via an injectable factory; tokens stored per game. |
| `SvgCardImage` | `CardImagePort` | Resolves `pinochle/card_images/fronts/<suit>_<rank>.svg` (or `png_96_dpi/…png`) and `backs/<name>.svg`. Holds the configured default back. Raises `FileNotFoundError` for missing artwork. |

### 4.5 The web layer (driving adapter)

```
pinochle/web/
├── main.py              # create_app(container); lifespan; pages; static mounts
├── container.py         # Settings, TableDefaults, Container, build_container
├── dependencies.py      # get_container, require_admin, require_admin_stream, require_seat
├── security.py          # token extraction; constant-time admin comparison
├── errors.py            # exception → HTTP status and JSON envelope
├── card_codec.py        # Card ⇄ "TS"; Suit ⇄ "SPADES"
├── event_encoder.py     # event → SSE frame
├── turn_header.py       # the public turn header on every frame
├── sse_stream.py        # retry line, stream headers, the queue → frame loop
├── transport_events.py  # SeatLost, SeatRejoined, GameAbandoned
├── schemas.py           # pydantic request and response bodies
└── routers/
    ├── admin.py         # §5.2
    ├── player.py        # §5.3
    ├── stream.py        # §6
    └── cards.py         # §5.4
```

No module in `pinochle/web/` contains a game rule. Routers authenticate,
decode, call a port method, and return `204` or a small JSON document. The
admin router's `start` check (every human seat has an open stream, FR-10b) and
its human-seat check before unlinking are transport facts, not rules: only the
web layer knows about connections.

`create_app(container=None)` builds the app; tests pass a container wired with
a `FakeScheduler` and a seeded shuffle. The module-level `app = create_app()`
is what uvicorn imports.

### 4.6 Composition root and configuration

`pinochle/web/container.py` holds the production wiring. `Settings.from_env()`
reads `.env` (via python-dotenv, never overriding the real environment) and the
`PINOCHLE_*` variables of §10.4; `build_container(settings, scheduler)` wires:

```python
state     = InMemoryGameState()
tokens    = InMemorySeatTokens()
scheduler = scheduler or AsyncioScheduler()
sse       = SseNotification(queue_maxsize=settings.sse_queue_maxsize)
notifier  = CompositeNotification([sse, LoggingNotification()])
rng       = Random(settings.shuffle_seed) if settings.shuffle_seed is not None else None
service   = GameService(state, notifier, scheduler, rng=rng,
                        trick_clear_seconds=settings.trick_clear_seconds)
driver    = ComputerDriver(service, state, scheduler, ComputerPlayerStrategy(rng=rng),
                           delay_seconds=settings.computer_delay_seconds)
notifier.append(driver)              # the driver observes every event (§7.1)
cards     = SvgCardImage(default_back=settings.card_back)
```

The `Container` exposes `admin` (the service), `actions` (the driver, so the
routers never know a seat is a computer), `state`, `sse`, `notifier`,
`tokens`, `scheduler`, `cards`, and `settings`. One `Random` feeds both the
shuffle and the computers' dealer-selection draws, which is what makes a
seeded game reproducible end to end (NFR-7).

`pinochle/app.py`'s `create_default_app()` is an older headless wiring
(`ImmediateScheduler`, `PrintNotification`, no driver). The web app does not
use it.

### 4.7 Concurrency model

The server runs on **one asyncio event loop in one process**:

- `GameStatePort` is in-memory and unsynchronised (NFR-8), and NFR-5 limits the
  system to one game, so there is nothing to gain from more workers. uvicorn
  must run with `--workers 1`: a second worker would hold a second, empty game
  store and a second SSE hub (NFR-11).
- Every route handler is `async def`, so no handler runs on a thread-pool
  worker, and service calls are made directly from the handler.
- Scheduler callbacks run on the same loop, so they never race a request.
- Because everything is serialised on one thread, the service's load → apply
  → dispatch → save cycle is atomic by construction. NFR-4's "left exactly as
  it was" reduces to raising before mutating, which the domain does.

### 4.8 Error handling

```
PinochleError
├── UnknownGameError    → 404  unknown_game
├── NotYourTurnError    → 409  not_your_turn
├── WrongPhaseError     → 409  wrong_phase       (includes any action during a pause)
├── IllegalActionError  → 409  illegal_action    (illegal card, bad bid, bad pass, taken position)
└── SetupError          → 409  setup_incomplete
```

`errors.py` registers handlers that render every failure as

```json
{ "error": { "code": "not_your_turn", "message": "It is p-south's turn to play." } }
```

A failed credential is `ForbiddenError` → `403 forbidden_seat` or
`forbidden_admin`. A malformed body is `422 invalid_request`, and so is any
`ValueError` a router raises — an unparseable card or suit code, an unknown
image format, a bad card-back name. Missing artwork is `404 not_found`.

### 4.9 Logging

`main.py`'s lifespan configures the root logger at `PINOCHLE_LOG_LEVEL` and
writes two startup lines: which `.env` was read, and — as a warning — the
admin token if it was generated. Thereafter:

- `pinochle.events` — `event.published game_id=… recipient=… event=…` for every
  delivery, from `LoggingNotification`, with hands redacted;
- `pinochle.stream` — `stream.opened` (with resume mode and replay length),
  `stream.closed`, `stream.replay_incomplete`, `stream.bad_last_event_id`;
- `pinochle.security` — `action.rejected reason=… path=… method=…` for every
  refused credential. The credential itself is never logged.

uvicorn runs with `--no-access-log`, because the stream URL carries a token.

---

## 5. HTTP API

### 5.1 Conventions

- Command endpoints live under `/api/`, take JSON, and return **`204 No
  Content`**; the result arrives on the event stream (RT-2, RT-3). Game
  creation returns `201` with the join links.
- **Seat authentication.** Player commands carry the seat token in an
  `X-Seat-Token` header. The stream carries it in `?t=`, because `EventSource`
  cannot set headers. The token is resolved against the path's `{game_id}`, so
  a token for another game is `403`.
- **Admin authentication.** Admin commands require `X-Admin-Token`, compared
  with `secrets.compare_digest`. Only the admin *stream* also accepts `?t=`; no
  mutating route does.
- **Card wire format.** Two characters: rank in `9 J Q K T A`, then suit in
  `S H D C`. `"TS"` is the ten of spades. The two copies of a card share a code
  (FR-19). `card_codec.py` owns both directions.
- **Suit wire format.** `"SPADES" | "HEARTS" | "DIAMONDS" | "CLUBS"`.
- **Seat wire format.** `"NORTH" | "EAST" | "SOUTH" | "WEST"`; player ids are
  `p-north` … `p-west` (FR-5).

### 5.2 Administrator endpoints

All require `X-Admin-Token` unless noted.

| Method | Path | Body | Effect |
| --- | --- | --- | --- |
| `GET` | `/api/admin/defaults` | — | The configured table the setup form starts from (FR-7a). |
| `POST` | `/api/admin/games` | teams + four seats | Creates the game, assigns teams, adds the four players, and mints a token per human seat. `201` with the game id and each seat's `join_url` (FR-6, FR-7, FR-10). |
| `GET` | `/api/admin/games/{id}` | — | The four seats: seat, player id, name, type, and `joined` (a computer, or a human with an open stream). |
| `POST` | `/api/admin/games/{id}/start` | — | `409 setup_incomplete` naming the seat unless every human seat has joined (FR-10b); then begins dealer selection (FR-9). |
| `POST` | `/api/admin/games/{id}/seats/{player_id}/unlink` | — | Human seats only. Revokes the seat's tokens, then closes its streams (RT-12a). |
| `POST` | `/api/admin/games/{id}/seats/{player_id}/computer` | — | Human seats only. Unlinks as above, then `AdminPort.seat_computer` (RT-12a). |
| `POST` | `/api/admin/games/{id}/abandon` | `{reason}` | Marks the game finished, broadcasts `game_abandoned`, revokes every token (RT-12b). |
| `GET` | `/api/admin/games/{id}/stream` | — | The console's SSE stream: broadcasts only. Token by header or `?t=`. |

Create request and response:

```json
{
  "teams": { "ns": "North-South", "ew": "East-West" },
  "seats": [
    { "seat": "NORTH", "name": "North", "type": "computer" },
    { "seat": "EAST",  "name": "East",  "type": "computer" },
    { "seat": "SOUTH", "name": "South", "type": "human" },
    { "seat": "WEST",  "name": "West",  "type": "computer" }
  ]
}
```

```json
{
  "game_id": "5c1f…",
  "seats": [
    { "seat": "NORTH", "name": "North", "type": "computer", "player_id": "p-north", "join_url": null },
    { "seat": "SOUTH", "name": "South", "type": "human",    "player_id": "p-south",
      "join_url": "http://localhost:8000/join/5c1f…?t=8Qk3…" },
    …
  ]
}
```

The join URL's host is `PINOCHLE_PUBLIC_BASE_URL`. Tokens are returned exactly
once and cannot be retrieved afterwards.

### 5.3 Player endpoints

All require `X-Seat-Token` and return `204`.

| Method | Path | Body | Port method | Requirements |
| --- | --- | --- | --- | --- |
| `POST` | `/api/games/{id}/draw` | `{"position": 17}` | `draw_for_deal` | FR-11, FR-11a |
| `POST` | `/api/games/{id}/bid` | `{"amount": 260}`, or `null`/omitted to pass | `place_bid` | FR-24–FR-30 |
| `POST` | `/api/games/{id}/contract` | `{"accept": true}` | `confirm_contract` | FR-32 |
| `POST` | `/api/games/{id}/trump` | `{"suit": "HEARTS"}` | `name_trump` | FR-34 |
| `POST` | `/api/games/{id}/pass` | `{"cards": ["AS","TS","KH","9C"]}` | `pass_cards` | FR-37–FR-43 |
| `POST` | `/api/games/{id}/begin-play` | — | `begin_play` | FR-50a |
| `POST` | `/api/games/{id}/toss-in` | — | `toss_in` | FR-50b |
| `POST` | `/api/games/{id}/play` | `{"card": "QS"}` | `play_card` | FR-51–FR-53 |
| `POST` | `/api/games/{id}/acknowledge` | `{"hold_id": 7}` | `acknowledge` | RT-13, UI-19a |
| `GET` | `/api/games/{id}/stream` | — | (SSE) | §6 |

`draw_for_deal` returns the card in its port signature; the router discards it
and the public `draw_made` event carries it to everyone, the drawer included
(FR-15). `begin-play` is refused while the meld hold stands; releasing that
hold is how play begins (FR-50a). There is no `GET` returning game state (RT-5).

### 5.4 Pages, static files, and artwork

| Path | Serves | Caching |
| --- | --- | --- |
| `GET /` | `frontend/public/index.html`; without a join link the page explains how to get one | `no-cache` |
| `GET /join/{game_id}` | the same page; the client reads `?t=` itself | `no-cache` |
| `GET /admin` | `admin.html`, with the setup form pre-filled from the configured table, and the token field filled when `?t=` is the valid admin token | `no-cache` |
| `GET /assets/*` | `frontend/public/` — HTML and CSS | `no-cache` (ETag revalidation) |
| `GET /static/*` | `frontend/dist/` — the compiled ES modules | `no-cache` |
| `GET /cards/faces/{code}?fmt=svg\|png` | a face by wire code | `immutable`, one year |
| `GET /cards/back?fmt=svg\|png` | the configured back (`PINOCHLE_CARD_BACK`) | `no-cache` |
| `GET /cards/backs/{name}?fmt=svg\|png` | a named back | `immutable`, one year |
| `GET /healthz` | `{"status":"ok"}` | — |

Pages, CSS and modules are unhashed file names (no bundler), so they are served
`no-cache` to force revalidation. Faces never change for a URL and are cached
for a year; a hand plus three fans of backs is about fifty images per render.
The configured back's URL is fixed while its content follows configuration, so
it revalidates. A missing page answers a JSON `404` telling the operator to run
`make build`.

### 5.5 Error catalogue

| Status | `code` | Raised when |
| --- | --- | --- |
| 403 | `forbidden_seat` | Missing, unknown, revoked, or wrong-game seat token |
| 403 | `forbidden_admin` | Missing or wrong admin token |
| 404 | `unknown_game` | No such game id |
| 404 | `not_found` | Artwork or a page missing from disk |
| 409 | `wrong_phase` | Action outside its phase, including during a trick clear, before dealer selection opens, or `begin-play` while the meld hold stands (RT-9) |
| 409 | `not_your_turn` | Right phase, wrong seat |
| 409 | `illegal_action` | Illegal card, invalid bid, wrong pass, position taken or out of range, second draw, unknown player, admin action on a computer seat |
| 409 | `setup_incomplete` | `start` before four players and two teams, or before every human seat has joined |
| 422 | `invalid_request` | Malformed body; unparseable card or suit code; unknown image format or back name |

---

## 6. Server-Sent Events

### 6.1 Why SSE

ARC-7 mandates SSE, and the shape of the game suits it: traffic is almost all
server → client, commands are small and infrequent, and HTTP's auth, proxy and
logging behaviour come free. No SSE library is used; a `StreamingResponse`
over an async generator is the whole implementation. The costs:

- one long-lived response per connection, which proxies must not buffer (§10.5);
- commands travel as separate POSTs, so their result is learned from the stream;
- `EventSource` cannot set headers, which puts the token in the query string;
- `EventSource` reconnects on its own, which the server turns to advantage by
  replaying what the seat missed (§6.9).

### 6.2 Connection lifecycle

```
client                                    server
  │ GET /api/games/{id}/stream?t=…         │
  │   [Last-Event-ID: 812 on a reconnect]  │
  ├───────────────────────────────────────►│ require_seat: token → player_id, or 403
  │                                        │ queue = hub.subscribe(game, player)     ┐ nothing awaited
  │                                        │ missed = hub.history_since(…, 812)      ┘ between these
  │                                        │ if the seat had no stream: broadcast seat_rejoined
  │ 200 text/event-stream                  │
  │◄───────────────────────────────────────┤ retry: 2000
  │◄───────────────────────────────────────┤ event: stream_started   (no id: line)
  │◄───────────────────────────────────────┤ the missed frames, in order
  │◄───────────────────────────────────────┤ live frames, and ": keepalive" when idle
  │                                        │
  │ (tab closed / network drop)            │
  ├───────────────────────────────────────►│ generator closes → hub.unsubscribe
  │                                        │ if that was the seat's last stream:
  │                                        │   broadcast seat_lost (RT-12)
```

Subscribing before reading the history, with no `await` between the two, means
the replay and the live queue meet exactly — no duplicate and no gap. That
matters because the client's reducer is not idempotent (a replayed `bid_placed`
would append a second bid).

Response headers: `Content-Type: text/event-stream`,
`Cache-Control: no-cache, no-transform`, `Connection: keep-alive`, and
`X-Accel-Buffering: no` so that nginx does not buffer the stream.

`stream_started` payload:

```json
{ "seat": "SOUTH", "player_id": "p-south",
  "you": { "name": "South", "type": "human" },
  "partial": false, "resume": "fresh" }
```

`resume` is `fresh` (no `Last-Event-ID`), `resumed` (the history reached back
far enough), or `incomplete` (it did not). `partial` is true when a round is in
progress and the replay was not whole.

The admin stream (`GET /api/admin/games/{id}/stream`) subscribes an admin
queue, sends `stream_started` with an empty payload, and then relays live
broadcasts. It does no replay.

The server ends a stream itself when the administrator unlinks the seat: the
hub puts a `STREAM_CLOSED` sentinel on each of the seat's queues, and the
generator returns and unsubscribes as if the client had left.

### 6.3 The hub

`SseNotification` owns the subscriber registry and the replay history:

```python
class SseNotification(NotificationPort):
    def __init__(self, queue_maxsize=256, history_maxlen=20000): ...
    # game_id → player_id → set of queues (FR-10c: several per seat)
    def subscribe(self, game_id, player_id) -> asyncio.Queue: ...
    def unsubscribe(self, game_id, player_id, queue) -> None: ...
    def subscribe_admin(self, game_id) -> asyncio.Queue: ...
    def unsubscribe_admin(self, game_id, queue) -> None: ...
    def close_seat(self, game_id, player_id) -> int: ...       # RT-12a
    def seats_connected(self, game_id) -> set[str]: ...
    def history_since(self, game_id, player_id, after_seq) -> (list, bool): ...
    def notify(self, player_id, event) -> None: ...             # one seat's queues
    def broadcast(self, game_id, event) -> None: ...            # every seat + admin
```

- Each dispatched event gets the next **per-game sequence number**, once,
  before fan-out, so `seq` is a single order shared by every seat and the
  console. A seat sees gaps where frames went to other seats.
- Queues carry `(seq, event)` pairs; encoding happens in the stream generator.
- **FR-10c holds by construction.** A seat's subscribers are a set of queues; a
  second tab adds one and displaces nothing. Either tab may act, because
  authorisation is by token.
- **Privacy is decided upstream.** The hub never inspects an event to decide
  who may see it; the service chose `notify` or `broadcast`.
- **The console sees exactly the broadcasts,** so it can never receive a hand.
- The history records each event's recipient (`None` for a broadcast), and
  `history_since` returns only broadcasts and the asking seat's own frames.

### 6.4 Frame format

Built by `event_encoder.py`:

```
id: 42
event: card_played
data: {"seq":42,"type":"card_played","turn":{…},"payload":{"player_id":"p-west","card":"KS"}}

```

- `event:` is the snake_case name, so the client subscribes per type.
- `id:` is the sequence number, which the browser sends back as
  `Last-Event-ID` when it reconnects. `stream_started` is sent with `seq` 0
  and no `id:` line, so a reconnect never winds the browser's marker back.
- `data:` is one line of JSON; `json.dumps` escapes embedded newlines.

**The turn header** is on every frame and says, publicly, where the game
stands *now*:

```json
"turn": {
  "phase": "PLAYING",
  "current_player_id": "p-south",
  "paused": "trick_clear",
  "hold": { "id": 7, "reason": "meld_exposed", "ackable": true },
  "round_number": 3
}
```

- `phase` is the round phase while a round is in progress, else the game phase
  (`SETUP`, `DEALER_SELECTION`, `FINISHED`).
- `current_player_id` is `Round.current_player`, or `null`.
- `paused` is `"trick_clear"` while a completed trick is on the table, else
  `null`.
- `hold` is the hold in force, or `null`.

`build_turn_header` reads the live `Game` rather than a snapshot taken at
dispatch. Readers are rarely more than a frame behind, and replayed frames are
folded before the client draws, so the header the client renders is current.

### 6.5 Event catalogue

**P** = broadcast to every seat and the console; **S** = one seat; **T** = the
two partners who exchanged cards.

| `event:` | Vis. | Payload | Requirement |
| --- | --- | --- | --- |
| `stream_started` | S | see §6.2 | RT-5a |
| `game_configured` | P | `seats: [{player_id, name, type, seat}]`, `teams: [{team_id, name}]`, `winning_score` | UI-1, UI-3 |
| `seat_replaced` | P | `{player_id, name, type}` | RT-12a |
| `dealer_selection_started` | P | `{spread_size: 48, taken: []}` | FR-11a, FR-14 |
| `draw_made` | P | `{player_id, position, card}` | FR-11, FR-15 |
| `draw_tied` | P | `{cards: {player_id: card}}` | FR-14 |
| `dealer_selected` | P | `{dealer_player_id}` | FR-13 |
| `round_started` | P | `{round_number, dealer_player_id}` | FR-16 |
| `cards_dealt` | S | `{cards: [12 codes]}` | FR-21, FR-22 |
| `turn_prompt` | S | phase-specific options, below | UI-9, UI-10 |
| `bid_placed` | P | `{player_id, amount \| null, current_high}` | FR-33 |
| `contract_offered` | P | `{player_id, amount}` | FR-32 |
| `round_abandoned` | P | `{declined_by \| null}` | FR-31, FR-32 |
| `trump_named` | P | `{suit}` | FR-36 |
| `cards_passed` | T | `{from_player_id, to_player_id, cards}` | FR-38, FR-40 |
| `meld_exposed` | P | `{player_id, cards, units: [{name, points, cards}], total}` | FR-44, FR-45 |
| `play_begun` | P | `{leader_player_id}` | FR-50a |
| `contract_tossed_in` | P | `{player_id}` | FR-50b |
| `seat_thinking` | P | `{player_id}` | RT-7, RT-10 |
| `card_played` | P | `{player_id, card}` | FR-57 |
| `trick_completed` | P | `{winner_player_id, cards: [{player_id, card}]}` | FR-54, UI-15 |
| `trick_cleared` | P | `{winner_player_id, next_leader_player_id \| null}` | UI-15, RT-10 |
| `round_scored` | P | `round_number, bid_team_id, bid_winner_player_id, contract, made_contract, tossed_in, teams: [{team_id, meld, card_points, last_trick_bonus, round_total, points_applied, cumulative_score}]` | FR-66 |
| `game_over` | P | `{winning_team_id, ns_score, ew_score}` | FR-71 |
| `hold_begun` | P | `{hold_id, reason, seconds, ackable}` | RT-10, RT-13 |
| `hold_ended` | P | `{hold_id, reason}` | RT-10, RT-13 |
| `seat_lost` | P | `{player_id}` | RT-12 |
| `seat_rejoined` | P | `{player_id}` | RT-12 |
| `game_abandoned` | P | `{reason}` | RT-12b |

`turn_prompt` is a tagged union on `phase`:

```json
{ "phase": "BIDDING",    "minimum_bid": 260, "may_pass": true }
{ "phase": "CONFIRMING", "amount": 250 }
{ "phase": "TRUMP" }
{ "phase": "PASSING",    "count": 4 }
{ "phase": "MELDING",    "may_begin_play": true, "may_toss_in": true }
{ "phase": "PLAYING",    "legal_plays": ["QS","JD","9H"] }
```

It is appended by `_load_save` after every operation that leaves a seat on the
clock during a round, and regenerated each time. Dealer selection has no prompt:
any undrawn seat may draw, and the public draw events say which positions are
taken. `legal_plays` comes from `Round.legal_plays`, so the client's highlight
and the server's check are the same computation (UI-9, FR-53).

### 6.6 Privacy, end to end

1. The domain emits `CardsDealt` once per player rather than one event holding
   four hands.
2. `GameService._recipients` maps each private event to its entitled seats.
3. `_dispatch` calls `notify` for those and `broadcast` for the rest.
4. The hub routes `notify` only to that seat's queues, and replays only a
   seat's own private frames.

`tests/services/test_event_privacy.py` asserts the property at the service
level. `LoggingNotification` redacts the two card-carrying private events so
the audit log is not a leak (NFR-9).

### 6.7 Pauses and holds

Every pause is a state the game occupies (RT-8, RT-9), delimited by events
(RT-10), and visible on every frame's turn header.

**Timed pauses** end by themselves and cannot be released:

| Pause | Opens with | On the header | Closes with | Length |
| --- | --- | --- | --- | --- |
| Trick clear (UI-15) | `trick_completed` | `paused: "trick_clear"` | `trick_cleared` | `PINOCHLE_TRICK_CLEAR_SECONDS`, 1.5 |
| Computer thinking (FR-75c) | `seat_thinking` | — | the seat's action event | `PINOCHLE_COMPUTER_DELAY_SECONDS`, 1.0 |

The trick clear is enforced by `Round`'s pending winner: `play_card` raises
`WrongPhaseError` until the scheduled `_clear_trick` runs.

**Holds** wait for any seated player (RT-13). Each is a `Hold` with an id and
`ackable=True`, begun with `game.begin_hold` (emitting `hold_begun`) and ended
by `acknowledge` (emitting `hold_ended`):

| `HoldReason` | Begun by | `_resume_from` then |
| --- | --- | --- |
| `DRAW_TIED` | a tied draw, after `draw_tied` | lays a fresh spread, `dealer_selection_started` |
| `DEALER_SELECTED` | a settled draw, after `dealer_selected` | deals the first round |
| `ROUND_ABANDONED` | four passes, after `round_abandoned` | rotates the deal, deals |
| `MELD_EXPOSED` | the second pass, after the four `meld_exposed` | `Round.begin_play` for the auction winner, `play_begun` |
| `ROUND_SCORED` | every scored round, after `round_scored` | deals the next round, or `game_over` |

Rules that hold throughout:

- A hold is begun only when the table has a human seat; otherwise the service
  does at once what the release would have done.
- While a hold stands, the computer driver schedules nothing (§7.2), and a
  computer seat never releases a hold.
- `toss_in` is accepted during the meld hold and ends it before scoring.
- `acknowledge` with a stale id succeeds and emits nothing; with an unknown
  player id it is `illegal_action`.
- `HoldReason` also defines `TRICK_CLEAR` and `THINKING`, and `Hold.timed`
  exists, but nothing begins a timed hold: the two timed pauses above are
  reported through `paused` and `seat_thinking` instead. The client folds
  `paused` into a hold-shaped value of its own (§8.3), so it treats both kinds
  the same way.

A client may POST at the moment an event makes its action illegal — clicking
a card just as a trick completes. The server arbitrates with a `409`, the
client shows the message briefly, and the stream, which alone drives the
display, has already moved on.

### 6.8 Keepalive and backpressure

**Keepalive.** After `PINOCHLE_SSE_KEEPALIVE_SECONDS` (15) with no frame, the
generator writes the comment `: keepalive`, so that an idle connection is not
reaped by a proxy — a table can sit on a hold for as long as the players talk.

**Backpressure.** Each queue is bounded at `PINOCHLE_SSE_QUEUE_MAXSIZE` (256). A
`put_nowait` that finds a queue full removes that queue from the fan-out, so
one reader that has stopped reading cannot hold up the others. See §15 for
what the dropped reader then sees.

### 6.9 Reconnection and replay

RT-5 forbids a snapshot; RT-5a requires a dropped client to recover. The hub's
per-game history (20,000 entries — several whole games) makes both true:

- The stream begins with `retry: 2000`, so `EventSource` retries two seconds
  after a drop, sending the last `id:` it saw as `Last-Event-ID`.
- The router replays every frame that seat was entitled to after that number,
  then goes live. The client folds them exactly as if they had arrived live.
- A tab opening a seat afresh — a second tab, a reload, or the join link
  reopened — has no `Last-Event-ID` and is replayed from the start of the game.
  Mid-game tabs therefore show the whole table.
- If the history no longer reaches back far enough, `resume` is `incomplete`,
  the log records it, and the client marks its view partial rather than fold a
  history with a hole in it.
- Replayed frames carry the current turn header, not the historical one; the
  client draws only after folding them all.

Seat presence is announced from the stream router: `seat_rejoined` when a
stream opens for a seat that had none (including its first join), `seat_lost`
when its last one closes. A seat with two tabs that closes one is not lost.

### 6.10 Worked sequence: a human card, answered by a computer

```
South's browser          server                                   all streams
      │ POST /play {"card":"QS"}
      ├──────────────────────────►│ require_seat → p-south
      │                           │ ComputerDriver.play_card → GameService
      │                           │   Round.play_card validates and mutates
      │                           │   CardPlayed(p-south, QS); TurnPrompt → p-west
      │                           │   dispatch → hub, log, driver
      │◄──────────────────────────┤ 204          card_played, turn.current = p-west ─►
      │                           │ driver.pump: West is a computer, no hold
      │                           │   note_seat_thinking → seat_thinking ──────────────►
      │                           │   scheduler.call_later(1.0, _act)
      │                   (1.0 s, counted by the server)
      │                           │ _act: SeatView → strategy.choose_play → play_card
      │                           │   CardPlayed(p-west, KS); the trick is complete
      │                           │   TrickCompleted(winner = p-west)
      │                           │                card_played, trick_completed,
      │                           │                turn.paused = "trick_clear" ──────►
      │                           │ scheduler.call_later(1.5, _clear_trick)
      │                   (1.5 s, counted by the server)
      │                           │ Round.clear_trick
      │                           │   TrickCleared(next_leader = p-west)
      │                           │                trick_cleared, turn.current = p-west ►
      │                           │ driver.pump: West leads → seat_thinking … and so on
```

---

## 7. Computer players

### 7.1 Shape

`ComputerDriver` (`pinochle/services/computer_driver.py`) plays two roles:

1. **A decorator over `PlayerActionPort`.** Every method delegates to
   `GameService`. The container hands the driver to the web layer as
   `actions`, so routers never know a seat is a computer.
2. **A `NotificationPort` observer.** Appended to the composite notifier, it
   sees every event, including those published by scheduler callbacks such as
   `TrickCleared`, which no decorator could intercept. After any event it asks
   whether a computer is now due to move.

Every point at which the turn can pass to a computer — a human's action, a
trick clearing, a hold released, a seat replaced, a round dealt — publishes an
event, so the single rule "after any event, look at whose turn it is" covers
them all.

### 7.2 The pump

```
pump(game):
    if a hold is in force:                   return
    if DEALER_SELECTION:
        for each undrawn computer seat, clockwise:  schedule(seat)
        return
    seat = Round.current_player, if a round is in progress
    if seat is a computer:                   schedule(seat)

schedule(seat):
    if (game, seat) is already pending:      return        # coalesce
    mark it pending
    service.note_seat_thinking(game, seat)                 # seat_thinking
    scheduler.call_later(delay, lambda: _act(game, seat))
```

- **Coalescing.** One cycle can publish several events (four `cards_dealt`,
  four `meld_exposed`); the pending set keeps one turn from being scheduled
  twice. `_act` clears the mark first.
- **Re-validation.** `_act` reloads the game and does nothing if the seat is no
  longer the one on the clock, or — in dealer selection — has already drawn.
- **Deferral is mandatory.** Dispatch runs *before* the service saves, so a
  synchronous `_act` would load a stale aggregate. `AsyncioScheduler` defers
  even at delay 0; `ImmediateScheduler` does not, which is why the web
  container never uses it.
- **Zero delay works** (FR-75c): with `AsyncioScheduler` an all-computer game
  runs as fast as the loop turns; with `FakeScheduler`, as fast as the test
  calls `advance(0)`.

### 7.3 Seat views keep FR-74 honest

`_act` builds a `SeatView` — player id, partner id, own hand, bid history,
current high bid, trump, cards in the current trick, every exposed meld, and
legal plays — and the strategy receives only its fields, never the `Game`. It
cannot read another hand because nothing it is given carries one. The driver
then calls the same `GameService` method a human's POST reaches, so FR-72 and
FR-73 are enforced by the same validation, and the resulting events are
indistinguishable (RT-6).

### 7.4 The shipped strategy

`ComputerPlayerStrategy` (`pinochle/strategies/computer_player_strategy.py`):

| Decision | Rule | Requirement |
| --- | --- | --- |
| Draw | a random untaken position, from the shared seeded `Random` | FR-11b |
| Bid | valuation = 180 + best suit's (meld + 15 per ace of the suit + 10 per card of the suit beyond four); bid the next increment while it is within the valuation | FR-75a |
| Bid against partner | once both opponents have passed, the partner with fewer bids gives way, unless it holds a whole run, which is worth one more bid | FR-75d |
| Lone contract | always accept | FR-75e |
| Trump | the longest suit | FR-75e |
| Pass | all trump, highest first; then unprotected aces; then the lowest unprotected cards; protected meld released lowest first only if needed. Used for both directions of the exchange | FR-75b |
| Meld | always begin play; never toss in | FR-75e |
| Play | the highest-ranked legal card | FR-75e |

The strategy is a constructor argument to the driver, which is what FR-75's
replaceability amounts to.

---

## 8. Front end

### 8.1 Layout

```
frontend/src/
├── main.ts      # player entry: resolve seat, open stream, fold, render; visible deal
├── admin.ts     # console entry: setup form, seat board, start / unlink / seat computer / abandon
├── types.ts     # the wire contract: Frame, TurnHeader, FRAME_TYPES
├── stream.ts    # EventSource wrapper; connection state; one listener per frame type
├── token.ts     # seat token from /join/{id}?t=…, admin token from /admin?t=…, sessionStorage
├── api.ts       # admin API calls; ApiError
├── actions.ts   # player POSTs
├── state.ts     # GameState and applyEvent(state, frame) — the reducer
├── cards.ts     # card codes, FR-23/FR-23a hand order, artwork URLs
├── layout.ts    # pure: seat placement, fan angles, spread scatter, legality, pause checks
├── view.ts      # pure: scoreboard lines, bid history, meld lines, summary, status line
├── notice.ts    # pure: the notice area's sentence and whether it offers Continue
├── deal.ts      # pure: the visible deal's packet order and projected state
├── table.ts     # renders the whole table from the state
├── hand.ts      # the viewer's own hand: fan, legality, click and drag, pass selection
├── spread.ts    # the scattered dealer-selection spread: drag to move, click to draw
├── panels.ts    # the action panel: bid, accept/decline, trump, pass tray, meld
└── log.ts       # the console's raw frame log
```

The pure modules (`state`, `cards`, `layout`, `view`, `notice`, `deal`) have no
DOM dependency, which is what lets them be tested under Node (§11).

### 8.2 Build

ARC-8 forbids a bundler and any runtime dependency; `tsc` alone satisfies it.
`tsconfig.json` targets ES2022 modules with `strict`,
`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` and
`verbatimModuleSyntax`, from `src/` to `dist/`. The Makefile runs
`npx -y -p typescript@5 tsc`, so no lockfile and no global install is needed.

The pages load the output as native modules
(`<script type="module" src="/static/main.js">`), so every relative import in
the source is written with a `.js` extension. Getting that wrong is a 404 at
run time, not a compile error.

### 8.3 State: one reducer, one render

```ts
state = applyEvent(state, frame);   // pure; never mutates its argument
render();                           // renderTable(state, callbacks)
```

`applyEvent` applies the frame type's handler, then refreshes `phase`,
`currentPlayerId`, `paused` and `hold` from the turn header, records the
highest `seq`, and drops a prompt the header no longer agrees with. The
header's `paused: "trick_clear"` is folded into `hold` as
`{id: null, reason: "trick_clear", ackable: false}`, so one `hold` field answers
"is the table paused, and can anyone release it?".

The state holds exactly what the events gave it: seats, teams and scores, the
spread and draws, the dealer, this seat's hand and every seat's hand count, bids
and the high bid, the offer and contract, trump, the pass sent and received,
meld per seat and per team, the trick, the last trick, tricks taken per team,
the thinking seat, the prompt, the round summary, and the game result. **It
holds no derived rule state:**

- it does not compute legal plays — it uses `turn_prompt.legal_plays` (UI-9);
- it does not decide who won a trick — it waits for `trick_completed`;
- it counts tricks per team, never card points; trick points enter the state
  for the first time with `round_scored` (UI-14c).

`seat_lost`, `seat_rejoined`, `game_abandoned`, `hold_begun` and `hold_ended`
are subscribed but change nothing: the holds are already on the header, and
the transport frames are not rendered on the table (§15).

`render` rebuilds the table each time; the table is a few dozen elements. The
two things a pointer can be holding — a card being dragged from the hand and a
spread card being moved — are not rebuilt under it, and the action panel and
notice are rebuilt only when their content changes, so a half-typed bid or a
Continue button under the pointer survives unrelated frames.

### 8.4 Geometry and rendering

**Stage (UI-17).** `#stage` is a fixed 1420 × 1000 layout scaled to the window
with one CSS `transform: scale()` whose ratio `main.ts` sets on resize.

**Seating (UI-1).** `layout.placement` puts this seat at the bottom, the next
clockwise seat on the left, the partner across, and the previous seat on the
right.

**Seats (UI-3, UI-5, UI-7).** Each seat shows its name (with "(dealer)"), a
partnership colour class, an italic name for a computer seat, a trailing "…"
while it is thinking, a highlight while it is acting, its drawn card during
dealer selection (FR-11d), a fan of backs sized from `handCounts`, its meld
grouped by combination while the phase is `MELDING`, and its latest call during
the auction.

**Hand order (FR-23, FR-23a).** `cards.sortHand` groups ♠♥♣♦, descending
A-T-K-Q-J-9. Once trump is named, trump leads and the others follow in
alternating colour, earlier FR-23 suit first. `trump_named` triggers
`noteResort`, which marks the hand so the re-sort is animated.

**Spread (FR-11c).** `layout.scatter` places each of the 48 backs once per
spread (keyed by `spreadId`), jittered in a grid over the felt and tilted up to
24°. `spread.ts` tells a press that travels (move the card, which then stays on
top) from one that does not (draw it).

**Trick (UI-6).** Played cards sit offset toward their players in the centre
layer until `trick_cleared`. The centre shows instead the round summary once
`round_scored` arrives and the final result once `game_over` does (UI-20).

**Scoreboard (UI-14, UI-14a).** A collapsible panel: team scores with this
round's meld beside them, round number, contract and bidder, trump, and the
score played to; beneath, each seat's meld (named until the first trick is
gathered, then totals only) and the bid history. Separate plaques on the felt
show the winning bid and the trump suit.

**Artwork (UI-16).** Faces are `/cards/faces/<code>`; backs are `/cards/back`,
so the configured back is the server's business.

### 8.5 Interaction

- **Play (UI-8, UI-9).** A legal card is clickable and draggable onto the trick
  layer; both end in the same `onPlay`. Illegal cards are dimmed and inert.
- **Pass (UI-12).** Clicking or dragging a card moves it from the hand into the
  pass tray; clicking or dragging it back returns it. Selection is by position
  in the hand, since a hand can hold both copies of a card. Confirm is enabled
  at exactly four. The opposing team never receives `cards_passed`, so hiding
  the exchange from them needs no client check.
- **Bid (UI-10).** A number field starting at the prompt's minimum, +10 and +50
  buttons, Bid, and Pass; a bad amount is refused locally before sending.
- **Lone contract (UI-10a).** Accept *n* or Decline.
- **Trump (UI-11).** Four suit buttons.
- **Meld (UI-12a).** For the auction winner: their side's meld, what is still
  needed in cards, and Play or Toss in. Play releases the meld hold when one
  stands, and calls `begin-play` directly only when none does.
- **Draw.** Click a spread card while this seat has not drawn.
- **Last trick (UI-14b).** A toggle beside the status line shows the previous
  trick over the current one; it closes itself when the next trick is cleared.
- **Refusals (NFR-4).** A rejected action shows the server's message in a toast
  that fades after four seconds.

Every action goes through one `attempt` wrapper that refuses to send while the
stream is not live (RT-5b).

### 8.6 Notices, connection status, and the visible deal

**Notice area (UI-19, UI-19a).** `notice(state)` returns one sentence, a kind
(`result`, `hold`, `final`), a key, and the hold id to release, if any. While a
hold stands it describes the hold ("Tied for high card - select again.",
"*name* deals.", "Everyone passed", "Review the meld laid out on the table.",
the round headline) and, if the hold is ackable, a Continue button that calls
`acknowledge` with its id. During the trick clear it says who takes the trick.
Otherwise it shows the newest concluded result: the round headline, a toss-in,
who took the last trick, the contract and trump, a lone bidder's offer, or who
deals — the pre-play announcements disappearing once a card is on the table.
The server sends no display text.

**Connection (RT-5b).** `stream.ts` reports `connecting`, `live`, `down`
(dropped, browser retrying), or `closed` (refused). `down` and `closed` show a
persistent banner, and actions are refused until `live` returns.

**Visible deal (FR-21a).** When `cards_dealt` arrives, `main.ts` shows the deal
as sixteen packets of three, 150 ms apart, clockwise from the dealer's left,
using `deal.dealingView` to project the state with no prompt. Frames arriving
meanwhile are queued and applied in order afterwards. This, the toast fade, and
the Copy button's label are the client's only timers (RT-8).

### 8.7 The seat token in the page

`token.resolveSeat` reads the game id from `/join/{id}` and the token from
`?t=`, mirroring the token into `sessionStorage` keyed by game. The token is
left in the address bar: a closed and reopened tab starts with empty
`sessionStorage`, and the link is the only copy of the token. `sessionStorage`
rather than `localStorage`, so four seats opened as four tabs of one browser
stay four seats.

### 8.8 The administrator's console

`admin.html` + `admin.ts`, styled by `style.css`:

- The token field is filled from `?t=` (or by the server when the page is
  served with a valid one) and remembered in `sessionStorage`.
- The setup form (team names; per seat a name and human/computer) is pre-filled
  by the server and refreshed from `GET /api/admin/defaults` once a token is
  known (FR-7a).
- Creating a game shows a seat board — seat, name, type, joined/waiting, the
  join link with a Copy button, and for human seats **Seat computer** and
  **Unlink**, each behind a confirmation — plus Start, Refresh and Abandon.
- The console opens the admin stream and shows every frame in a raw log. A
  `seat_lost`, `seat_rejoined` or `seat_replaced` frame refreshes the seat
  board by itself (RT-12). For an all-computer table this log is the only way
  to watch the game.
- A `forbidden_admin` failure is explained: where the token comes from, and
  that `/admin?t=<token>` fills it in.

---

## 9. The administrator's workflow

The administrator stands the server up and turns four names into a game. They
cannot see a hand, act for a seat, or alter a score; their authority is at the
boundaries — setup, repair, and ending a game.

### 9.1 Standing up the server

- **Development:** `make dev` builds the client and runs uvicorn on
  `127.0.0.1:8000` with reload, admin token `dev`, and prints the console link
  `http://localhost:8000/admin?t=dev`.
- **Container:** copy `.env.example` to `.env`, set `PINOCHLE_ADMIN_TOKEN` and
  `PINOCHLE_PUBLIC_BASE_URL`, then `make docker`. Left unset, the admin token is
  generated at startup and logged as a warning (`make docker-logs`); it changes
  on every restart. See `docs/docker-usage.md`.

State is in memory (NFR-8) and the process is single-worker (§4.7), so a
restart — including a `--reload` in development — destroys any game in
progress.

### 9.2 Creating the game

Open `/admin?t=<token>`, adjust the pre-filled form, and Create. Each human
seat gets a join link. **A join link is a credential** (FR-10a): anyone holding
it can see that hand and play those cards. Distribute them privately, one each;
they are shown once and cannot be retrieved. An administrator who also plays
opens their own seat's link in an ordinary tab.

`make seed` does the same from the command line (South human by default;
`make seed-watch` for four computers, `make seed-all` for four humans), and
starts the game once every human tab is open.

### 9.3 Starting play

Start is refused, naming the seat, until every human seat has an open stream
(FR-10b). A seat whose player will not be coming can be given to the computer
first. Once started, the game runs itself: draws, ties, the deal, the auction,
and scoring need nothing from the administrator. The only waits are players'
decisions and holds, which the players release themselves (RT-13).

### 9.4 During the game

The console shows public events and each seat's connection. If a player drops,
the seat board shows them waiting, play blocks at their seat, and they can
rejoin by reopening their link (RT-5a). If they are not coming back, **Seat
computer** hands the seat over and play resumes from where it stopped; if the
last human seat is replaced while a hold stands, the hold is released at once
(RT-12a). **Unlink** cuts off a player's link without seating anyone. **Abandon**
ends the game with a reason and revokes every link (RT-12b); starting again
means creating a new game.

### 9.5 Tuning

`PINOCHLE_TRICK_CLEAR_SECONDS` (UI-15) and `PINOCHLE_COMPUTER_DELAY_SECONDS`
(FR-75c) set the pace, per server rather than per game. `make dev-fast` sets
both to zero.

---

## 10. Packaging and deployment

### 10.1 What the image contains

One image runs the whole system: the FastAPI server, the card artwork, and the
compiled client. There is no database and no second service (NFR-8, NFR-11).

### 10.2 `docker/Dockerfile`

Two stages:

1. `node:22-slim` copies `frontend/package.json`, `tsconfig.json` and `src/`,
   and runs `npx -y -p typescript@5 tsc`. The client is always compiled here, and
   `.dockerignore` excludes `frontend/dist`, so the image cannot ship a stale
   build.
2. `python:3.12-slim` installs the package with `pip install .` (NFR-2), copies
   `frontend/public` and the compiled `dist`, sets
   `PINOCHLE_FRONTEND_DIR=/app/frontend`, runs as an unprivileged `pinochle`
   user, and has a `urllib`-based `HEALTHCHECK` on `/healthz`.

```
CMD ["uvicorn", "pinochle.web.main:app", "--host", "0.0.0.0", "--port", "8000",
     "--workers", "1", "--timeout-keep-alive", "75", "--no-access-log"]
```

`--workers 1` is load-bearing (§4.7). `--timeout-keep-alive 75` exceeds the
keepalive interval. `--no-access-log` keeps stream URLs, which carry a token,
out of the log.

### 10.3 `docker/compose.yaml`

One service, `pinochle`, built from the repository root, `restart:
unless-stopped`, reading `../.env` as its `env_file`, and publishing
`${PINOCHLE_BIND_ADDRESS:-127.0.0.1}:${PINOCHLE_PORT:-8000}:8000`. Binding to
loopback by default is deliberate: a reverse proxy on the host is the expected
way in. No volume is mounted; there is nothing to persist. The Makefile's
`docker`, `docker-logs` and `docker-down` targets wrap it.

### 10.4 Configuration

Read by `Settings.from_env()` from the environment, then `.env` for anything
the environment does not set (NFR-10). `.env.example` documents every key.

| Variable | Default | Effect | Requirement |
| --- | --- | --- | --- |
| `PINOCHLE_ADMIN_TOKEN` | generated per run and logged | Console credential | FR-6 |
| `PINOCHLE_PUBLIC_BASE_URL` | `http://localhost:8000` | Host part of join links | FR-10 |
| `PINOCHLE_TRICK_CLEAR_SECONDS` | `1.5` | Trick-clear pause | UI-15 |
| `PINOCHLE_COMPUTER_DELAY_SECONDS` | `1.0` | Computer delay; `0` for full speed | FR-75c |
| `PINOCHLE_CARD_BACK` | `blue` | Bundled back by plain name (`castle`, `frog`, `red2`, …); a path is refused at startup | UI-16 |
| `PINOCHLE_TEAM_NS`, `PINOCHLE_TEAM_EW` | `North-South`, `East-West` | Setup form's team names | FR-7a |
| `PINOCHLE_SEAT_<SEAT>_NAME` | `North` … `West` | Setup form's seat names | FR-7a |
| `PINOCHLE_SEAT_<SEAT>_TYPE` | South `human`, others `computer` | Setup form's seat kinds; anything but `human`/`computer` is refused at startup | FR-7a |
| `PINOCHLE_LOG_LEVEL` | `INFO` | Log level | NFR-9 |
| `PINOCHLE_SSE_KEEPALIVE_SECONDS` | `15` | Keepalive interval | §6.8 |
| `PINOCHLE_SSE_QUEUE_MAXSIZE` | `256` | Per-connection queue bound | §6.8 |
| `PINOCHLE_FRONTEND_DIR` | `frontend` | Where `public/` and `dist/` are found | §3 |
| `PINOCHLE_SHUFFLE_SEED` | unset | Seeds the shuffle and computer draws | NFR-7 |
| `PINOCHLE_BIND_ADDRESS`, `PINOCHLE_PORT` | `127.0.0.1`, `8000` | Compose port binding only; not read by Python | — |

The default setup-form values also appear in `admin.html`, so the page is
sensible before the server fills it; `tests/web/test_table_defaults.py` holds
the two copies to each other.

### 10.5 Behind a reverse proxy

A proxy must not buffer or compress `text/event-stream`. The server sends
`X-Accel-Buffering: no`, which nginx honours; the location also wants
`proxy_http_version 1.1`, an empty `Connection` header, `proxy_buffering off`,
`proxy_cache off`, and a long `proxy_read_timeout`, since a table can sit on a
hold for a long time. The proxy's access log should omit or strip the `t`
query parameter. `docs/docker-usage.md` gives a complete Caddy-fronted VPS
deployment.

---

## 11. Testing

**Server** (`make test-py`, pytest, `asyncio_mode = "auto"`). `tests/` mirrors
the package:

- `domain/` — cards, deck, hand legality, bidding, meld detection, tricks,
  scoring, holds (NFR-3).
- `ports/` — the ABCs' contracts.
- `adapters/` — each adapter, including the hub's fan-out, sequence numbers,
  replay filtering and `close_seat`, and the fake scheduler's clock.
- `services/` — `Round`, `GameService` events, holds and their release,
  event privacy, the computer driver's pump and seat views.
- `strategies/` — bidding valuation, yielding to a partner, passing.
- `web/` — every router through `httpx.ASGITransport` against
  `create_app(container)` with a `FakeScheduler`; the status-code mapping;
  the encoder and turn header; the stream's replay and resume modes; the
  pages; table defaults; and an end-to-end all-computer game driven to
  `game_over` on the fake clock.

No test sleeps: every pause is advanced on the fake scheduler (ARC-10).

**Client** (`make test-fe`). `tsc` compiles, then `node --test test/*.test.js`
runs against `dist/`: the reducer (`state`), a replay of a recorded seat stream
(`replay`, using `test/fixtures/seat-stream.json`), hand order (`cards`),
layout, notices, view text, and the visible deal. `make record` regenerates the
fixture from a real all-computer game through the real service and encoder
(`scripts/record_frames.py`), so it cannot drift from the wire format.

**Reachability** (`make test-browser`, needs Chrome). `scripts/hit_test.py`
serves `test/browser/reachability.html`, which replays the recorded stream
through the real reducer, renderer and stylesheet and, after every frame, asks
what a click aimed at each enabled control would actually hit (UI-18).

---

## 12. Dependencies

```toml
dependencies = [
    "pytest", "pytest-mock", "pytest-asyncio",
    "fastapi", "uvicorn[standard]", "httpx", "python-dotenv",
]
```

Test tools sit in `[project.dependencies]`, so `pip install -e .` is enough to
run everything (NFR-2). There is no SSE library. The client has no runtime
dependency; `typescript` is its only (build-time) devDependency.

---

## 13. Tooling

The Makefile is the entry point for development (`make help` lists it):

| Target | Does |
| --- | --- |
| `make test` | `test-py` and `test-fe` |
| `make test-browser` | build, then the Chrome reachability check |
| `make build` / `make watch` | compile the client once / on every save |
| `make dev` / `make dev-fast` | run the server locally with reload / with every pause at zero |
| `make seed` / `seed-watch` / `seed-all` | create and start a game from the command line |
| `make record` | re-record the client's replay fixture |
| `make docker` / `docker-logs` / `docker-down` | the container |
| `make clean` | remove build and test artefacts |

The server was built in this order, each step leaving the suite green: domain
events; the error hierarchy; the scheduler adapters; seat tokens; the
notification adapters and encoder; the web layer; the computer driver (step 7,
at which point an all-computer game ran end to end over HTTP with no browser);
the front end; Docker; and polish. `docs/impl.md` records the front-end slices.

---

## 14. Design decisions

**14.1 Replay instead of snapshots.** RT-5 forbids a server-built snapshot, and
RT-5a requires recovery. Keeping the dispatched events per game, tagged with
their recipient, satisfies both: a client's view is still built only from
events, but it can be handed the events it missed. The same mechanism makes a
second tab opened mid-game show the whole table, which a live-only stream
could not.

**14.2 The turn header and `turn_prompt`.** Deriving whose turn it is or which
cards are legal on the client would violate ARC-2, so the server states both:
the public turn, pause and hold on every frame, and private options to the
acting seat.

**14.3 `seat_lost`, `seat_rejoined`, and `game_abandoned` are transport-level
events.** The domain knows nothing of connections and should not. These three
are published by the stream router and the admin router, not by `Game`, and
live in `pinochle/web/transport_events.py`.

**14.4 One hold concept, released by anyone.** A hold names a pause; any one
seated player releases it; a release names its hold so a late click does
nothing; and a hold never times out, because a timer would resume the game
while the players are still reading. Requiring all four, or the
administrator, would make the table slower than the conversation around it.

**14.5 No hold without a human.** A hold at an all-computer table could never
end. The service tests the seats' kind, not their connection, so a human seat
that has gone quiet still blocks — that is RT-12's case, remedied by seating
a computer, which releases the hold if it was the last human.

**14.6 The seat token travels in the stream URL.** `EventSource` cannot set
headers, and FR-10a makes the token the only credential. Mitigations: uvicorn's
access log is off, the application never logs tokens, and a proxy should strip
`t` from its log. The token is left in the address bar deliberately (§8.7).

**14.7 One process, one worker.** NFR-5 and NFR-8 let the design commit to a
single event loop in a single worker, and take the simplicity that buys: no
locks and atomic operation cycles. It is invisible in the code and fatal to
violate.

**14.8 Artwork is served by the server.** The card images ship inside the
Python package and are resolved through `CardImagePort`, so that a
configured back is a server setting and a face is addressed by the same code
the stream uses.

**14.9 A cosmetic deal.** The server sends each hand whole; the client shows it
arriving three cards at a time. The animation is presentation only, queues
frames rather than dropping them, and decides nothing, so RT-8's rule that the
client holds no timers affecting the game still stands.

---

## 15. Known limitations

These are behaviours of the current code that fall short of what a reader of
the requirements might expect, recorded so they are not mistaken for intent.

1. **The player's table does not render `seat_lost`, `seat_rejoined` or
   `game_abandoned`.** Only the console reacts to them. A player waiting on an
   absent seat sees a table that is simply waiting, and after an abandon their
   stream stays open but silent while their actions start failing with
   `forbidden_seat`.
2. **A dropped slow reader is not told.** When a queue overflows it is removed
   from the fan-out, but its generator keeps writing keepalives, so the client
   still reports itself live while receiving no events. No `stream_broken` frame
   is sent.
3. **The thinking mark can linger.** `seat_thinking` sets the thinking seat,
   and only `card_played` or a new round clears it, so after a computer bids,
   names trump or passes, the "…" stays on its name until the next
   `seat_thinking`. The server never sets `paused: "thinking"`, although the
   turn header supports it.
4. **Rule rejections and accepted actions are not logged.** Only published
   events, refused credentials and stream lifecycle are. The lifespan's
   docstring still mentions `action.accepted`.
5. **FR-64 tests trick points, not tricks.** A non-bidding team whose tricks
   held only Jacks and Nines, and did not include the last, scores nothing even
   though it took a trick.
6. **The auction winner passes trump back.** The computer's pass selection is
   the same in both directions, so a computer auction winner gives its partner
   its trump.
7. **`HoldReason.TRICK_CLEAR`, `HoldReason.THINKING` and `Hold.timed` are
   unused.** The timed pauses are reported another way (§6.7).
8. **`pinochle/app.py` is vestigial.** `create_default_app` predates the web
   container and is not used by it.
9. **Unlink is still offered after the game is over.** Seating a computer is
   refused then, but unlinking is not.
