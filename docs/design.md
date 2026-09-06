# Pinochle — Design

**Status:** Draft
**Last updated:** 2026-09-06
**Implements:** `docs/requirements.md`

---

## 1. Purpose and scope

`docs/requirements.md` says *what* the system must do. This document says *how*
it will be built. Every section cites the requirement identifiers it satisfies,
so that the two documents can be read side by side and any drift between them is
visible.

It covers:

- the split of the code base into a Python **server** and a TypeScript
  **front end** that live in separate top-level directories (§3);
- the server's internal structure as a ports-and-adapters application (§4);
- the HTTP surface for commands (§5);
- the Server-Sent Events architecture that pushes state to clients (§6);
- how computer players are driven (§7);
- the browser client (§8);
- the administrator's workflow for standing up and running a game (§9);
- packaging and deployment with Docker (§10);
- testing, dependencies, and a suggested build order (§11–§13).

Where the design has had to make a decision the requirements did not settle, or
where implementing a requirement exposed a gap in another, §14 records it.

---

## 2. Design principles

### 2.1 The dependency rule

```
╔══════════════════════════════════════════════════════════════════════════╗
║  DRIVING SIDE (INBOUND)                                                  ║
║                                                                          ║
║   Browser client (TypeScript)      Admin console (TypeScript)            ║
║              │  HTTP POST                    │  HTTP POST                ║
║              ▼                               ▼                           ║
║   ┌──────────────────────────────────────────────────────┐               ║
║   │  pinochle/web/  — FastAPI driving adapter            │               ║
║   │  routers: admin · player · stream                    │               ║
║   │  (no game logic; translates HTTP ⇄ ports)            │               ║
║   └──────────────────────────────────────────────────────┘               ║
╚═══════════════════════════════│══════════════════════════════════════════╝
                                │ calls
                                ▼
╔══════════════════════════════════════════════════════════════════════════╗
║  APPLICATION LAYER                                                       ║
║                                                                          ║
║   GameService  (implements AdminPort + PlayerActionPort)                 ║
║   ComputerDriver (decorates PlayerActionPort; observes NotificationPort) ║
║   Round        (round state machine)                                     ║
║                                                                          ║
║   depends only on these ABCs:                                            ║
║     AdminPort · PlayerActionPort          (driving)                      ║
║     GameStatePort · NotificationPort ·    (driven)                       ║
║     SchedulerPort · SeatTokenPort                                        ║
╚═══════════════════════════════│══════════════════════════════════════════╝
                                │ implemented by
                                ▼
╔══════════════════════════════════════════════════════════════════════════╗
║  DRIVEN SIDE (OUTBOUND ADAPTERS)                                         ║
║                                                                          ║
║   InMemoryGameState      → GameStatePort                                 ║
║   SseNotification        → NotificationPort   (fan-out to seat queues)   ║
║   LoggingNotification    → NotificationPort   (NFR-9 audit log)          ║
║   CompositeNotification  → NotificationPort   (tees to the above)        ║
║   AsyncioScheduler       → SchedulerPort      (production)               ║
║   FakeScheduler          → SchedulerPort      (tests, virtual clock)     ║
║   InMemorySeatTokens     → SeatTokenPort                                 ║
╚═══════════════════════════════│══════════════════════════════════════════╝
                                │ uses
                                ▼
╔══════════════════════════════════════════════════════════════════════════╗
║  DOMAIN LAYER (pure; no I/O, no frameworks)                              ║
║                                                                          ║
║   Card · Rank · Suit · Deck · Hand · Trick                               ║
║   Player · Position · Team · BiddingRound · MeldUnit                     ║
║   Game (aggregate root + domain events) · scoring functions              ║
╚══════════════════════════════════════════════════════════════════════════╝
```

**Data flow:** browser gesture → `POST /api/games/{id}/…` → web router
authenticates the seat token and decodes the body → `PlayerActionPort` method →
`ComputerDriver` delegates to `GameService` → `GameService` loads the `Game`,
executes the requested domain operation through `Round`, drains the emitted
events → the
composite notifier logs them and hands each one to the SSE hub → the hub places
it on every subscribed queue that the event's recipient list permits → each
`GET /api/games/{id}/stream` generator serialises it as an SSE frame → the
client reduces the frame into its table state and re-renders. The HTTP response
to the original POST carries no game data: it is `204 No Content` (RT-2).

**Dependency rule:** the application layer (`pinochle/services/`) may import
from `pinochle/domain/` and `pinochle/ports/`, and nothing else. It may not
import FastAPI, Starlette, `asyncio`, `time`, `logging` handlers, `json`,
`uuid`-over-the-wire formats, or any module under `pinochle/adapters/` or
`pinochle/web/` (ARC-1, ARC-9).

### 2.2 The client renders; it never decides

ARC-2 and RT-8 are enforced by three habits, applied throughout §6 and §8:

1. Every command endpoint returns `204`. The client learns the outcome only when
   the corresponding event arrives on its stream.
2. The client holds no timers that affect what it displays. Both timed pauses —
   the trick clear (UI-15) and the computer delay (FR-75c) — are counted by the
   server and delimited by a pair of events (RT-10).
3. The client is *told* what is legal rather than deriving it. The server sends
   the acting seat a private `turn_prompt` event carrying the legal plays, the
   minimum bid, or whichever options that phase offers (UI-9, §6.5).

---

## 3. Repository layout

The server and the front end are kept in separate top-level trees. The Python
package contains application code only; every browser-facing asset, including
card artwork, belongs under `frontend/`. Nothing under `frontend/` is imported
by Python, and nothing under `pinochle/` is compiled by `tsc`. The runtime
contract between them is the HTTP + SSE surface described in §5 and §6.

```
$PROJECT_ROOT/
├── pinochle/                  # SERVER — the Python package (unchanged root)
│   ├── domain/                # pure game logic
│   ├── ports/                 # ABCs, one per module
│   ├── services/              # application layer
│   ├── adapters/              # driven adapters
│   ├── web/                   # FastAPI driving adapter  (new)
│   └── app.py                 # composition root
│
├── frontend/                  # FRONT END — everything the browser runs
│   ├── package.json           # devDependency: typescript (build-time only)
│   ├── tsconfig.json
│   ├── public/                # hand-written static assets, served as-is
│   │   ├── index.html         # the player's table page
│   │   ├── admin.html         # the administrator's console
│   │   ├── cards/             # all card artwork (browser-owned, §5.4)
│   │   │   ├── fronts/        # card faces, named by wire code (e.g. QS.svg)
│   │   │   └── backs/         # card backs (e.g. blue.svg)
│   │   └── styles/
│   ├── src/                   # TypeScript sources
│   └── dist/                  # tsc output — generated, git-ignored
│
├── tests/                     # server tests (pytest), mirrors pinochle/
├── docker/
│   ├── Dockerfile
│   └── compose.yaml
├── docs/
│   ├── requirements.md
│   └── design.md              # this document
└── pyproject.toml
```

Two boundary notes:

- **Card artwork belongs to the front end.** Faces and backs live only under
  `frontend/public/cards/` alongside the other browser-facing static assets.
  The browser loads them directly from `/assets/cards/…` (§5.4); the Python
  application neither resolves nor packages image files.
- **The served document root is `frontend/`.** The server serves the HTML pages
  from `frontend/public/`, mounts that directory at `/assets/`, and mounts
  `frontend/dist/` at `/static/`. The path is configurable
  (`PINOCHLE_FRONTEND_DIR`) so that the container can place the built assets
  wherever it likes without the Python code caring.

---

## 4. Server design

### 4.1 Domain layer

The domain is already largely in place: `Card`, `Rank`, `Suit`, `Deck`, `Hand`,
`Trick`, `Player`/`Position`, `Team`, `BiddingRound`, `detect_meld`, the scoring
functions, and the `Game` aggregate with its event list. Partnership membership
is derived from `Position.team_id` and never stored, which is what makes FR-4a
hold by construction.

The design adds the following to `pinochle/domain/game.py`, each because a
requirement needs a client to be told something the current event set does not
carry. Each is a frozen dataclass in the same style as the existing events:

| New event | Why |
| --- | --- |
| `GameConfigured` | The client cannot draw the table (UI-1, UI-3) without the four seats, names, human/computer flags, and team names. |
| `DealerSelectionStarted` | Carries the spread size so the client can lay out the 48 face-down positions (FR-11a). |
| `DrawMade` | FR-15: each drawn card is revealed to all players. `draw_for_deal` currently returns the card to the caller and tells nobody else. |
| `DrawTied` | FR-14: everyone must see that the draw is being repeated, and with a fresh spread. |
| `RoundStarted` | Round number and dealer, so the client can reset the table between rounds. |
| `ContractOffered` | FR-32: the lone bidder's client must know to show accept/decline, and the other three must know why play has paused. |
| `PlayBegun` | FR-50a: ends the meld display for all four clients. |
| `CardPlayed` | FR-57 and RT-4 both require it; only `TrickCompleted` exists today, which would leave three of the four cards invisible until the trick ended. `Trick`'s internal record of the same name is renamed `TrickPlay` so the event can own the name. |
| `TrickCleared` | RT-10: the closing bracket of the trick-clear pause (UI-15). `_clear_trick` currently emits nothing. Its `next_leader_player_id` is the winner (FR-56), or `None` after the twelfth trick. |
| `SeatThinking` | RT-10 again: the opening bracket of a computer player's delay (FR-75c, RT-7). |

Two existing events are enriched:

- **`RoundScored`** must carry, per team, the recorded meld, the captured card
  points, the last-trick bonus, the round total, the points actually applied,
  and the new cumulative score, together with a flag for whether the bidding
  team made the contract or went set (FR-66). Its present `ns_score`/`ew_score`
  pair is not enough to render the round summary. Each team's line is a
  `TeamRoundScore`, a frozen dataclass in its own module
  `pinochle/domain/team_round_score.py` (ARC-3). The round total and the points
  applied are separate figures because they diverge precisely when the round is
  interesting: a team that goes set has a positive round total and a negative
  application (FR-63), and a non-bidding team that took no trick has a positive
  round total and applies zero (FR-64). `scoring.py` gains one pure function,
  `score_card_points`, so that captured points and the last-trick bonus can be
  reported separately; `score_tricks` is refactored to compose it and keeps its
  behaviour.
- **`GameOver`** carries both final cumulative scores alongside the winning team
  id (FR-71).

`GamePhase` and `RoundPhase` already model the phase machine of §3 of the
requirements, including `CONFIRMING` and `ABANDONED`.

### 4.2 Ports

Existing server ports retained by this design: `AdminPort`, `PlayerActionPort`,
`GameStatePort`, `NotificationPort`, and `SchedulerPort`.

`CardImagePort` is retired. Card artwork is presentation data owned and resolved
by the browser, so it does not cross an application-layer boundary and does not
need a server port. The existing `SvgCardImage` adapter and
`pinochle/card_images/` package are removed when the front end is introduced;
the artwork moves to `frontend/public/cards/`.

One port is added, in its own module per ARC-3/ARC-4:

```python
# pinochle.ports.seat_token_port
class SeatTokenPort(ABC):
    """Mints and resolves the opaque per-seat credentials of FR-10."""

    @abstractmethod
    def mint(self, game_id: str, player_id: str) -> str:
        """Create and store an unguessable token for one seat."""

    @abstractmethod
    def resolve(self, game_id: str, token: str) -> str | None:
        """Return the player id the token seats, or None if it is not valid."""

    @abstractmethod
    def revoke_game(self, game_id: str) -> None:
        """Forget every token issued for a finished or abandoned game."""
```

Token generation belongs behind a port for the same reason shuffling does
(NFR-7): tests need it deterministic, production needs it unguessable.

### 4.3 Application layer

**`GameService`** keeps its present shape and its `load → execute domain
operation → dispatch events → save` discipline. Its `_recipients` static
method is the single place where event privacy is decided (RT-1, NFR-6), and it
already routes `CardsDealt` to one player and `CardsPassed` to the two partners.
The new events fit the same rule: all are public except `turn_prompt` (§6.5),
which is addressed to one seat.

Changes needed:

- emit the new events listed in §4.1 at the points where they occur;
- accept `trick_clear_seconds` as a constructor argument rather than reading the
  module constant, so §10.4's environment variable can reach it;
- accept a `Random` instance for shuffling, so NFR-7's seeding is wired rather
  than global.

**`ComputerDriver`** (new, `pinochle/services/computer_driver.py`) drives the
computer seats. It is described in full in §7.

**`Round`** is unchanged except for the events its callers now emit.

### 4.4 Driven adapters

| Adapter | Port | Notes |
| --- | --- | --- |
| `InMemoryGameState` | `GameStatePort` | Exists. NFR-8: state is memory-only and a restart loses the game. |
| `SseNotification` | `NotificationPort` | New. Owns the per-seat subscriber queues; see §6.3. Deals in `GameEvent` objects, not JSON — serialisation is the web layer's job. |
| `LoggingNotification` | `NotificationPort` | New. NFR-9: logs every published event tagged with the game id, at `INFO`. Redacts `CardsDealt.cards` and `CardsPassed.cards` to counts, so the log is not itself a leak. |
| `CompositeNotification` | `NotificationPort` | New. Holds a list of notifiers and forwards to each in order, so the service still depends on exactly one port. |
| `AsyncioScheduler` | `SchedulerPort` | New. `loop.call_later(delay, callback)`; a delay of `0` becomes `loop.call_soon`, which still defers to a later tick (this matters — see §7). |
| `FakeScheduler` | `SchedulerPort` | New, used by tests. Holds `(due_at, callback)` pairs against a virtual clock and runs them when `advance(seconds)` is called (ARC-10). |
| `ImmediateScheduler` | `SchedulerPort` | Exists. Kept for headless domain-level drivers only; it is *not* suitable once the computer driver is wired, because running a callback synchronously re-enters an in-flight `load/dispatch/save` cycle. |
| `InMemorySeatTokens` | `SeatTokenPort` | New. `secrets.token_urlsafe(32)`, stored in a nested dict keyed by game id. Constructor takes a token factory so tests can inject a deterministic one. |

### 4.5 The web layer (driving adapter)

```
pinochle/web/
├── __init__.py
├── main.py            # ASGI app factory; lifespan; static mounts
├── container.py       # the wired object graph for the process
├── dependencies.py    # FastAPI dependencies: admin auth, seat auth, game id
├── security.py        # token extraction from header or query string
├── errors.py          # domain exception → HTTP response mapping
├── card_codec.py      # Card ⇄ wire string ("AS", "TH", "9C")
├── event_encoder.py   # GameEvent → SSE frame (name, id, JSON data)
├── schemas.py         # pydantic request/response models
└── routers/
    ├── admin.py       # §5.2
    ├── player.py      # §5.3
    └── stream.py      # §6
```

No module in `pinochle/web/` contains a game rule. Routers do exactly four
things: authenticate, decode, call a port method, and return `204` or a small
JSON document. ARC-7 requires it of the SSE endpoint specifically; the design
applies it to the whole package.

`main.py` exposes `create_app(container: Container | None = None) -> FastAPI`
so that tests can substitute a container built with `FakeScheduler` and a seeded
`Random`. The module-level `app = create_app()` is what uvicorn imports.

### 4.6 Composition root and configuration

`pinochle/app.py` grows a `Settings` dataclass, read once from the environment
(§10.4), and a `build_container(settings)` function that wires the graph:

```python
state      = InMemoryGameState()
tokens     = InMemorySeatTokens()
scheduler  = AsyncioScheduler()
sse        = SseNotification()
notifier   = CompositeNotification([sse, LoggingNotification()])
service    = GameService(state, notifier, scheduler,
                         trick_clear_seconds=settings.trick_clear_seconds,
                         rng=Random(settings.shuffle_seed))
driver     = ComputerDriver(service, state, scheduler, ComputerPlayerStrategy(),
                            delay_seconds=settings.computer_delay_seconds)
notifier.append(driver)          # the driver observes events (§7)
actions    = driver              # the web layer's PlayerActionPort
```

`create_default_app()` is kept as the headless wiring used by CLI drivers and
integration tests.

### 4.7 Concurrency model

The whole server runs on **one asyncio event loop in one process**. This is a
deliberate constraint, not an accident:

- `GameStatePort` is in-memory and unsynchronised (NFR-8), and `NFR-5` limits the
  system to one game at a time, so there is nothing to gain from more workers and
  a great deal to lose.
- The container **must** be run as `uvicorn --workers 1`. A second worker would
  get its own empty `InMemoryGameState` and its own SSE hub, and half the seats
  would silently see a different game.

Consequences the implementation must respect:

1. **Every route handler is `async def`.** A `def` handler is run by Starlette in
   a thread-pool worker, which would let two mutations of the same `Game` overlap
   and would make `queue.put_nowait` a cross-thread call. There is no
   synchronisation anywhere in the domain or services, and none is wanted.
2. **Service calls are made directly from the handler.** They are pure in-memory
   work — a deal, a meld detection, a trick resolution — measured in microseconds,
   so they do not need to be pushed off the loop.
3. **Scheduler callbacks run on the same loop thread**, via `loop.call_later`, so
   they never race with a request handler.
4. Because everything is serialised on one thread, `GameService`'s
   `load → execute domain operation → dispatch events → save` cycle is atomic
   by construction. NFR-4's "the game state shall be left exactly as it was"
   then reduces to: raise before changing state, which the domain already does.

### 4.8 Error handling

Domain and service code raises `ValueError` with a human-readable message today.
The design introduces a small exception hierarchy in `pinochle/domain/errors.py`
so that the web layer can map failures to status codes without string-matching:

```
PinochleError
├── UnknownGameError        → 404  unknown_game
├── NotYourTurnError        → 409  not_your_turn
├── WrongPhaseError         → 409  wrong_phase
├── IllegalActionError      → 409  illegal_action   (illegal card, bad bid, …)
└── SetupError              → 409  setup_incomplete
```

`errors.py` in the web layer registers one exception handler that renders every
`PinochleError` as

```json
{ "error": { "code": "not_your_turn", "message": "It is South's turn to play." } }
```

Authentication failures are `403 forbidden_seat`; a malformed body is FastAPI's
own `422`. In every case the game state is untouched, because the exception is
raised before any mutation and no partial state is saved (NFR-4).

### 4.9 Logging

A single `pinochle` logger tree, configured in `main.py`'s lifespan from
`PINOCHLE_LOG_LEVEL` (NFR-9). Three record types, each carrying `game_id`:

- `action.accepted` — the port method, the seat, and the decoded arguments.
- `action.rejected` — the same, plus the error code and message.
- `event.published` — the event name and its recipients.

`LoggingNotification` redacts card lists in `CardsDealt` and `CardsPassed`, and
`security.py` never logs a token. Both rules are part of NFR-9's requirement that
the log not become a leak of private state.

---

## 5. HTTP API

### 5.1 Conventions

- All command endpoints live under `/api/`, take JSON, and return **`204 No
  Content`** on success. Nothing about the resulting game state comes back in the
  response; it arrives on the client's event stream (RT-2, RT-3).
- **Seat authentication.** Every player endpoint requires the seat token of
  FR-10a. Commands carry it in an `X-Seat-Token` header. The SSE endpoint carries
  it in the `?t=` query parameter, because `EventSource` cannot set request
  headers — see §6.2 for the consequences.
- **Admin authentication.** Admin endpoints require `X-Admin-Token`, compared
  against `PINOCHLE_ADMIN_TOKEN` with `secrets.compare_digest`.
- **Card wire format.** A two-character code: rank in `9 J Q K T A` followed by
  suit in `S H D C`. `"TS"` is the ten of spades. The two physical copies of a
  card are interchangeable (FR-19), so a card needs no instance identity on the
  wire. `card_codec.py` owns the encoding in both directions.
- **Suit wire format.** `"SPADES" | "HEARTS" | "DIAMONDS" | "CLUBS"`.
- **Seat wire format.** `"NORTH" | "EAST" | "SOUTH" | "WEST"`.

### 5.2 Administrator endpoints

| Method | Path | Body | Effect |
| --- | --- | --- | --- |
| `POST` | `/api/admin/games` | seats + team names | Creates the game and seats all four players in one call (FR-6, FR-7). Returns the game id and, for each human seat, its token and join URL (FR-10). |
| `GET` | `/api/admin/games/{game_id}` | — | Setup status: the four seats, and for each human seat whether a stream is currently open. |
| `POST` | `/api/admin/games/{game_id}/start` | — | Validates seating and begins dealer selection (FR-9). |
| `POST` | `/api/admin/games/{game_id}/abandon` | `{reason}` | Ends a game that cannot be completed; broadcasts `game_abandoned` and revokes the tokens (RT-12). |
| `GET` | `/api/admin/games/{game_id}/stream` | — | The admin's own SSE stream: public events plus seat join/loss notices. Carries no hand. |

`POST /api/admin/games` composes the existing `AdminPort` methods —
`create_game`, `assign_teams`, four `add_player` calls — inside one request. The
port keeps its fine-grained shape; the router provides the convenient surface.

Request:

```json
{
  "teams": { "ns": "Us", "ew": "Them" },
  "seats": [
    { "seat": "NORTH", "name": "Phil",   "type": "human" },
    { "seat": "EAST",  "name": "Ada",    "type": "computer" },
    { "seat": "SOUTH", "name": "Grace",  "type": "human" },
    { "seat": "WEST",  "name": "Turing", "type": "computer" }
  ]
}
```

Response `201`:

```json
{
  "game_id": "5c1f…",
  "seats": [
    { "seat": "NORTH", "name": "Phil",  "type": "human",
      "player_id": "p-north",
      "join_url": "https://pinochle.example/join/5c1f…?t=8Qk3…" },
    { "seat": "EAST",  "name": "Ada",   "type": "computer", "player_id": "p-east" },
    …
  ]
}
```

The join URL's host comes from `PINOCHLE_PUBLIC_BASE_URL` (§10.4) so that the
links work behind a reverse proxy. The tokens are returned exactly once, at
creation; they are not retrievable afterwards.

`start` rejects with `409 setup_incomplete` unless there are four distinct seats
and two teams (FR-9) **and** every human seat has at least one open stream
(FR-10b). The admin's console shows the join board so this is never a surprise
(§9).

### 5.3 Player endpoints

All require `X-Seat-Token`; all return `204`. The path's `{game_id}` must match
the token's game, or the request is `403`.

| Method | Path | Body | Port method | Requirements |
| --- | --- | --- | --- | --- |
| `POST` | `/api/games/{id}/draw` | `{"position": 17}` | `draw_for_deal` | FR-11, FR-11a, FR-12 |
| `POST` | `/api/games/{id}/bid` | `{"amount": 260}` or `{"amount": null}` | `place_bid` | FR-24–FR-30 |
| `POST` | `/api/games/{id}/contract` | `{"accept": true}` | `confirm_contract` | FR-32 |
| `POST` | `/api/games/{id}/trump` | `{"suit": "HEARTS"}` | `name_trump` | FR-34 |
| `POST` | `/api/games/{id}/pass` | `{"cards": ["AS","TS","KH","9C"]}` | `pass_cards` | FR-37–FR-43 |
| `POST` | `/api/games/{id}/begin-play` | — | `begin_play` | FR-50a |
| `POST` | `/api/games/{id}/toss-in` | — | `toss_in` | FR-50b |
| `POST` | `/api/games/{id}/play` | `{"card": "QS"}` | `play_card` | FR-51–FR-53 |
| `GET` | `/api/games/{id}/stream` | — | (SSE) | §6 |

`draw_for_deal` returns the drawn card to its caller in the port signature; the
router discards that return value and lets the resulting `DrawMade` event carry
it to all four clients, so that the drawing player and the watchers learn it by
the same route (FR-15).

Note what is **not** here: there is no `GET` that returns the game state. That
absence is RT-5 and it is deliberate — see §6.9.

### 5.4 Static and asset endpoints

| Path | Serves |
| --- | --- |
| `GET /` | `frontend/public/index.html` |
| `GET /join/{game_id}` | The same table page; the `?t=` token is read by the client from `location.search` and then removed from the address bar with `history.replaceState`. |
| `GET /admin` | `frontend/public/admin.html` |
| `GET /static/*` | `frontend/dist/` — the compiled ES modules |
| `GET /assets/*` | `frontend/public/` — stylesheets, fonts, and card artwork |
| `GET /healthz` | `{"status":"ok"}` for the container health check (§10) |

Card faces and backs are ordinary static front-end assets under
`frontend/public/cards/`. They do not have a Python route or pass through an
application port. Requests below `/assets/cards/` are served with
`Cache-Control: public, max-age=31536000, immutable`; an artwork filename must
therefore change whenever its contents change.

### 5.5 Error catalogue

| Status | `code` | Raised when |
| --- | --- | --- |
| 403 | `forbidden_seat` | Missing, unknown, or wrong-game seat token |
| 403 | `forbidden_admin` | Bad admin token |
| 404 | `unknown_game` | No such game id |
| 409 | `wrong_phase` | Action submitted outside its phase, including during a timed pause (RT-9) |
| 409 | `not_your_turn` | Right phase, wrong seat |
| 409 | `illegal_action` | Illegal card, invalid bid, wrong number of cards passed, position already taken |
| 409 | `setup_incomplete` | `start` before seating or joining is finished |
| 422 | — | Malformed JSON or an unparseable card/suit code (FastAPI) |

---

## 6. Server-Sent Events architecture

### 6.1 Why SSE, and what it costs

ARC-7 mandates SSE, and the shape of the game justifies it: traffic is almost
entirely server → client, commands are small and infrequent, and HTTP semantics
(auth, proxies, logging) come free. The costs the design must pay for are:

- one long-lived response per connection, so the server must not buffer it;
- no client → server channel on the same connection, so commands go over separate
  POSTs (§5.3), and their ordering relative to the stream matters (§6.7);
- `EventSource` cannot set headers, which forces the token into the query string
  (§6.2);
- `EventSource` reconnects automatically on a drop, which the design must
  actively suppress, because reconnection is out of scope (§6.9).

### 6.2 Connection lifecycle

```
client                                   server
  │  GET /api/games/{id}/stream?t=…       │
  ├──────────────────────────────────────►│  security.py resolves the token
  │                                       │  → player_id, or 403 and done
  │                                       │
  │                                       │  hub.subscribe(game_id, player_id)
  │                                       │    → a new asyncio.Queue
  │  200, text/event-stream               │
  │◄──────────────────────────────────────┤  retry: 86400000
  │  event: stream_started                │  (suppress auto-reconnect, §6.9)
  │◄──────────────────────────────────────┤
  │                                       │
  │  event: … (for the life of the game)  │
  │◄──────────────────────────────────────┤
  │                                       │
  │  (tab closed / network drop)          │
  ├──────────────────────────────────────►│  generator cancelled
  │                                       │  hub.unsubscribe(...)
  │                                       │  if that was the seat's last stream:
  │                                       │    broadcast seat_lost (RT-12)
```

The response carries `Content-Type: text/event-stream`,
`Cache-Control: no-cache, no-transform`, `Connection: keep-alive`, and
`X-Accel-Buffering: no` — the last so that an nginx in front of the container
does not buffer the stream into uselessness (§10.5).

**On the token in the query string.** It is the only option `EventSource` leaves
open without inventing a second credential, which FR-10a forbids. The design
mitigates it: the server never logs query strings (§4.9), §10.5 configures the
reverse proxy to strip `t` from its access log, and the client removes the token
from the address bar immediately after reading it. Deployments that terminate TLS
are the assumed case; over plain HTTP the token is exposed exactly as any bearer
credential would be.

### 6.3 The hub

`SseNotification` implements `NotificationPort` and owns the subscriber
registry. It handles `GameEvent` objects; it does no serialisation, so the
domain's event types never acquire a wire representation.

```python
class SseNotification(NotificationPort):
    def __init__(self, queue_maxsize: int = 256):
        # game_id → player_id → set of queues (FR-10c: several per seat)
        self._seats: dict[str, dict[str, set[Queue[Envelope]]]] = {}
        self._admins: dict[str, set[Queue[Envelope]]] = {}

    def subscribe(self, game_id, player_id) -> Queue: ...
    def unsubscribe(self, game_id, player_id, queue) -> None: ...
    def seats_connected(self, game_id) -> set[str]: ...

    def notify(self, player_id: str, event: GameEvent) -> None:
        """Deliver to every queue belonging to one seat."""

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Deliver to every queue in the game, plus the admin queues."""
```

Three properties fall out of this shape:

- **FR-10c holds by construction.** A seat's subscribers are a *set* of queues.
  Opening the seat in a second tab adds a queue; it does not displace the first,
  and both receive every event addressed to the seat. Either tab may then act,
  because authorisation is by token, not by connection.
- **Privacy is decided upstream.** The hub never inspects an event to decide who
  may see it. `GameService._recipients` has already made that call by choosing
  `notify` over `broadcast` (RT-1, NFR-6). The hub only routes.
- **The admin's stream sees exactly the broadcasts.** Since every private event
  goes out through `notify`, subscribing the admin queues to `broadcast` alone
  guarantees the admin console can never receive a hand, whatever it asks for.

### 6.4 Frame format

Each frame is produced by `event_encoder.py`:

```
id: 42
event: card_played
data: {"seq":42,"type":"card_played","turn":{...},"payload":{...}}

```

- `event:` is the snake_case event name, so the client attaches one listener per
  type rather than switching inside a single handler.
- `id:` is a per-game monotonic sequence number, assigned by the encoder as it
  serialises. It exists for ordering assertions in tests and for reading logs. It
  is **not** a resume cursor: the server ignores `Last-Event-ID` entirely (§6.9).
- `data:` is one line of compact JSON. The encoder must escape any embedded
  newline, since a newline would terminate the frame.

**The turn header.** Every frame carries a `turn` object describing public,
non-private table state as it stands *after* the event:

```json
"turn": {
  "phase": "PLAYING",
  "current_player_id": "p-south",
  "paused": "trick_clear",
  "round_number": 3
}
```

This is the smallest thing that keeps the client honest. Without it, a client
would have to re-derive whose turn it is from the rules — which is exactly what
ARC-2 forbids. Everything in the header is information a player at a physical
table can see, so it is safe on a broadcast frame. `paused` is `null`, or the
name of the pause the game is currently sitting in (§6.7).

### 6.5 Event catalogue

Legend: **P** = public, broadcast to all four seats and the admin; **S** = sent
to one seat; **T** = team-private, sent to two seats.

| `event:` name | Vis. | Payload | Requirement |
| --- | --- | --- | --- |
| `stream_started` | S | `{seat, player_id, you: {…}}` — who this stream belongs to | §6.2 |
| `game_configured` | P | seats, names, human/computer, team names, target score | UI-1, UI-3, UI-14 |
| `dealer_selection_started` | P | `{spread_size: 48, taken: []}` | FR-11a |
| `draw_made` | P | `{player_id, position, card}` | FR-11, FR-15 |
| `draw_tied` | P | `{cards: {player_id: card}}` then a fresh `dealer_selection_started` | FR-14 |
| `dealer_selected` | P | `{dealer_player_id}` | FR-13 |
| `round_started` | P | `{round_number, dealer_player_id}` | FR-16 |
| `cards_dealt` | S | `{cards: [12 codes]}` | FR-21, FR-22, NFR-6 |
| `turn_prompt` | S | phase-specific options — see below | UI-9, UI-10 |
| `bid_placed` | P | `{player_id, amount \| null, current_high}` | FR-33 |
| `contract_offered` | P | `{player_id, amount}` | FR-32 |
| `round_abandoned` | P | `{declined_by \| null}` | FR-31, FR-32 |
| `trump_named` | P | `{suit}` | FR-36 |
| `cards_passed` | T | `{from_player_id, to_player_id, cards}` | FR-38, FR-40 |
| `meld_exposed` | P | `{player_id, units: [{name, cards, points}], total}` | FR-44, FR-45 |
| `play_begun` | P | `{leader_player_id}` | FR-50a |
| `contract_tossed_in` | P | `{player_id}` | FR-50b |
| `seat_thinking` | P | `{player_id}` — a computer seat's delay has begun | RT-7, RT-10 |
| `card_played` | P | `{player_id, card}` | FR-57 |
| `trick_completed` | P | `{winner_player_id, cards: [{player_id, card}]}` | FR-54, UI-15 |
| `trick_cleared` | P | `{winner_player_id, next_leader_player_id}`, the latter `null` after the twelfth trick | UI-15, RT-10 |
| `round_scored` | P | round number, contract, bid team, `made_contract`, `tossed_in`; per team: meld, card points, last-trick bonus, round total, points applied, cumulative | FR-66 |
| `game_over` | P | `{winning_team_id, ns_score, ew_score}` | FR-71 |
| `seat_lost` | P | `{player_id}` — that seat has no open stream | RT-12 |
| `seat_rejoined` | P | `{player_id}` — a stream opened for a seat that had none | RT-12 |
| `game_abandoned` | P | `{reason}` — the administrator has ended it | RT-12 |

`turn_prompt` is the mechanism by which the client displays options without
knowing rules. Its payload is a tagged union on the phase:

```json
{ "phase": "BIDDING",  "minimum_bid": 260, "may_pass": true }
{ "phase": "TRUMP" }
{ "phase": "CONFIRMING", "amount": 250 }
{ "phase": "PASSING",  "count": 4 }
{ "phase": "MELDING",  "may_begin_play": true, "may_toss_in": true }
{ "phase": "PLAYING",  "legal_plays": ["QS","JD","9H"] }
{ "phase": "DEALER_SELECTION", "taken": [3, 17, 40] }
```

It is emitted to exactly one seat whenever the current player changes, and it is
regenerated (not resumed) at each change. `legal_plays` comes straight from
`Round.legal_plays`, so the highlight in the client and the check on the server
are the same computation — UI-9 and FR-53 cannot disagree.

### 6.6 Privacy, end to end

The chain that satisfies RT-1 and NFR-6 has four links, and every one of them
lives on the server:

1. The domain emits `CardsDealt` once per player rather than one event holding
   four hands.
2. `GameService._recipients` maps each private event to its entitled seats.
3. `_dispatch` calls `notify` for those, `broadcast` for everything else.
4. The hub routes `notify` only to that seat's queues.

A test asserts the property directly: run a full round, capture every frame
written to each of the four streams, and assert that no frame delivered to seat
*X* contains a card code that was in another seat's `cards_dealt`, except cards
that later appear in a public `card_played`, `meld_exposed`, or a `cards_passed`
that *X* was party to. `tests/services/test_event_privacy.py` already establishes
this at the service level; the design extends it to the encoded frames.

### 6.7 Timed pauses are states, not effects

RT-8 through RT-11 say a pause is a real state the game occupies. The design
represents each pause as a bracketing pair of events, with the `turn` header's
`paused` field set in between:

| Pause | Opens with | `paused` value | Closes with | Length |
| --- | --- | --- | --- | --- |
| Trick clear (UI-15) | `trick_completed` | `"trick_clear"` | `trick_cleared` | `PINOCHLE_TRICK_CLEAR_SECONDS`, default 1.5 |
| Computer thinking (FR-75c) | `seat_thinking` | `"thinking"` | the action event itself (`bid_placed`, `card_played`, …) | `PINOCHLE_COMPUTER_DELAY_SECONDS`, default 1.0 |

Consequences:

- The client's rule stays "render what the last event said" (RT-10). It never
  starts a timer, and it never predicts when a pause will end.
- All four clients change state on the same server-published event, so they
  cannot drift apart (RT-11).
- **A pause rejects actions.** `Round.play_card` already raises when
  `_pending_winner is not None` — "The completed trick has not been cleared yet."
  That is RT-9: the next leader cannot play into a table that still holds the last
  trick, and the attempt returns `409 wrong_phase` like any other out-of-phase
  action.
- The pause is counted by `SchedulerPort` (ARC-9), so a test advances the fake
  clock rather than sleeping (ARC-10).

There is one ordering subtlety worth stating. A client may fire a POST at almost
the same moment an event arrives that makes the action illegal — for instance
clicking a card just as the trick-clear pause begins. The server is the
arbiter: the POST is rejected with `409`, the client shows the rejection
briefly, and the stream, which is the only thing that drives the display, has
already moved on. The client never needs to reconcile the two, because the POST
response carries no state (§5.1).

### 6.8 Keepalive, backpressure, and slow readers

**Keepalive.** Every `PINOCHLE_SSE_KEEPALIVE_SECONDS` (default 15) with no
traffic, the generator writes an SSE comment line `: keepalive`. Comments are
ignored by `EventSource` and by proxies alike, but they keep an idle connection
from being reaped — and a Pinochle table can be idle for minutes while a human
thinks (`MELDING` and `CONFIRMING` are untimed by design).

**Backpressure.** Each queue is bounded at `PINOCHLE_SSE_QUEUE_MAXSIZE` (default
256). If a `put_nowait` raises `QueueFull`, the subscriber is hopelessly behind;
the hub drops that queue, and the generator writes a final `stream_broken` frame
and closes. Dropping is the only honest response: without a replay journal
(§6.9) a client that skipped an event can never be correct again, and it is
better to say so than to render a table that has quietly diverged.

**Never block the loop.** The generator awaits its own queue and writes to the
socket; a client that stops reading exerts TCP backpressure on that one
generator, which is why the bounded queue and the drop rule exist. No other
seat's delivery is affected.

### 6.9 Disconnection: no reconnection, and how that is enforced

RT-5 is unambiguous: a client builds its view from the stream it has been
receiving since it joined, the server constructs no point-in-time snapshot, and
a client that loses its stream cannot rebuild one. RT-12 says the seat is then
gone for good, and the other three must be told so they can abandon the game
deliberately.

The design enforces this rather than merely refraining from implementing it:

- **No state endpoint exists.** There is no `GET /api/games/{id}` for players
  (§5.3). The one admin `GET` returns setup metadata only, never cards.
- **No journal is kept.** The hub holds queues, not history. Nothing in the
  process can reconstruct a mid-game view for a new subscriber.
- **`Last-Event-ID` is ignored.** The stream router does not read the header.
- **Auto-reconnect is suppressed.** The first thing the stream writes is
  `retry: 86400000`, setting `EventSource`'s reconnection delay to a day. On
  `stream_broken` the client also calls `es.close()`, so the browser does not
  spin through a reconnect loop against a server that cannot help it.
- **Seat loss is announced.** When a seat's *last* queue is removed, the hub
  broadcasts `seat_lost`. It is the last queue, not any queue, because FR-10c
  allows a seat several concurrent connections and closing one of two tabs must
  not report the seat as gone. Clients render a persistent banner naming the
  lost seat; the administrator's console offers the abandon action (§5.2, §9).

The one case this leaves rough is a second tab opened *mid-game*: it is
authorised (FR-10c) and it receives every subsequent event, but it missed the
deal and cannot draw the hand. Its `stream_started` frame carries
`"partial": true`, and the client shows "this view joined mid-game" instead of a
table. §14.1 records the tension between FR-10c and RT-5 that produces this, and
what would change if RT-5 were relaxed.

### 6.10 Worked sequence: one card, played by a human, answered by a computer

```
South's browser          server                                 all four streams
      │  POST /play {"card":"QS"}
      ├───────────────────────────►│ security: token → p-south
      │                            │ ComputerDriver.play_card → GameService
      │                            │   Round.play_card validates and mutates
      │                            │   emit CardPlayed(p-south, QS)
      │                            │ _dispatch → broadcast
      │◄───────────────────────────┤ 204
      │                            │                    event: card_played ──►
      │                            │                    turn.current = p-west
      │                            │
      │                            │ driver observes the event; West is a
      │                            │ computer → scheduler.call_later(1.0, act)
      │                            │   emit SeatThinking(p-west)
      │                            │                    event: seat_thinking ─►
      │                            │                    turn.paused = "thinking"
      │                            │
      │                     (1.0s, counted by the server)
      │                            │ driver acts: legal_plays → strategy → play
      │                            │   emit CardPlayed(p-west, KS)
      │                            │                    event: card_played ───►
      │                            │ trick now complete
      │                            │   emit TrickCompleted(winner=p-west)
      │                            │                    event: trick_completed ►
      │                            │                    turn.paused="trick_clear"
      │                            │ scheduler.call_later(1.5, clear)
      │                     (1.5s, counted by the server)
      │                            │   Round.clear_trick
      │                            │   emit TrickCleared(next_leader=p-west)
      │                            │                    event: trick_cleared ──►
      │                            │                    turn.current = p-west
```

Every visible change in every browser is the direct consequence of a frame on
this diagram. No client computed a delay, decided a winner, or guessed a turn.

---

## 7. Computer players

### 7.1 Shape

`ComputerDriver` is an application-layer object that plays two roles:

1. **A decorator over `PlayerActionPort`.** It implements every method by
   delegating to `GameService`. This is what the web layer is given, so the
   routers depend on the port and know nothing about computer seats.
2. **A `NotificationPort` observer.** It is appended to the composite notifier,
   so it sees every event the service publishes — including those from the
   service's own scheduler callbacks, such as `TrickCleared`, which no decorator
   could intercept.

Being an observer is what makes the driver complete. Every point at which the
turn can pass to a computer seat — a human's action, a trick clearing, a round
being scored and the next dealt, dealer selection starting — publishes an event,
so a single "after any event, look at whose turn it is" rule covers all of them.

### 7.2 The pump

On observing an event for game *G*, the driver calls `pump(G)`:

```
if a pump is already pending for G:      return          # coalesce
if the game is FINISHED or ABANDONED:    return
seat = whose turn is it (from the Game aggregate)
if seat is None or seat is HUMAN:        return
mark a pump pending for G
emit SeatThinking(seat)                                  # opens the pause
scheduler.call_later(delay_seconds, lambda: self._act(G, seat))
```

Three details matter:

- **Coalescing.** One `load → execute domain operation → dispatch events →
  save` cycle can publish several events — four `CardsDealt`, then four
  `MeldExposed`. Without the pending flag
  the driver would schedule several callbacks for the same turn. The flag is
  cleared in `_act`, after the action has been submitted.
- **Deferral is mandatory.** The driver must never act synchronously inside
  `_dispatch`, because dispatch runs *before* `GameService` saves the game; a
  synchronous re-entry would load a stale aggregate and then be overwritten by
  the outer save. `AsyncioScheduler` guarantees deferral even at delay `0`, by
  falling back to `loop.call_soon`. `ImmediateScheduler` does not, which is why
  §4.4 marks it unsuitable once the driver is wired.
- **Zero delay works.** FR-75c requires the delay be reducible to zero for
  all-computer test games. With `AsyncioScheduler` the game then runs as fast as
  the loop can turn, and with `FakeScheduler` it runs as fast as the test calls
  `advance(0)`.

### 7.3 Seat views keep FR-74 honest

`_act` builds a `SeatView` — a small frozen dataclass holding only what that seat
is entitled to: its own hand, the public bid history, the trump if named, the
cards on the table, the exposed meld, the legal plays. The strategy receives the
`SeatView` and nothing else. It is never handed the `Game`, so it *cannot* read
another hand; FR-74 is a property of the type signature rather than a discipline.

The driver then calls the same `PlayerActionPort` method a human client's POST
would reach, so FR-72 and FR-73 are enforced by exactly the same validation, and
the resulting events are indistinguishable to clients (RT-6).

### 7.4 The shipped strategy

`ComputerPlayerStrategy` exists and covers draw, trump, pass, and play. FR-75a
and FR-75b ask for more than it currently does:

- **Bidding (FR-75a)** — new. Estimate = detected meld for each candidate trump
  suit + a conservative trick estimate from aces held and length in that suit.
  Bid up to the estimate in 10s; pass above it. The strategy must be given the
  current high bid and whether it is the opener.
- **Passing (FR-75b)** — replace "the four lowest" with: pass trump and aces that
  support the contract while retaining cards that complete the passer's own meld.
- **Trump and play** — the existing heuristics stand for this release.

FR-75 requires only that the logic be replaceable, and it is: the strategy is a
constructor argument to the driver. Selectable difficulty is out of scope.

---

## 8. Front end

### 8.1 Layout

```
frontend/
├── package.json               # devDependency: typescript. No runtime deps.
├── tsconfig.json
├── public/
│   ├── index.html
│   ├── admin.html
│   └── styles/
│       ├── table.css          # green felt, seats, fan geometry (UI-2)
│       └── admin.css
├── src/
│   ├── main.ts                # player entry point
│   ├── admin.ts               # admin console entry point
│   ├── net/
│   │   ├── stream.ts          # EventSource wrapper; typed per-event dispatch
│   │   └── actions.ts         # fetch() wrappers for the POST endpoints
│   ├── model/
│   │   ├── events.ts          # TS interfaces mirroring §6.5 exactly
│   │   ├── table_state.ts     # reduce(state, event) → state
│   │   ├── cards.ts           # code parsing, FR-23/FR-23a sort order
│   │   └── seating.ts         # own seat → left/across/right mapping
│   ├── view/
│   │   ├── table.ts           # top-level render(state)
│   │   ├── seats.ts           # names, partnership colours, turn marker
│   │   ├── hand.ts            # own fan; legality highlight
│   │   ├── opponents.ts       # fanned backs, correct counts
│   │   ├── trick.ts           # four positioned cards
│   │   ├── spread.ts          # 48 face-down dealer-selection positions
│   │   ├── bidding.ts, trump.ts, passing.ts, meld.ts
│   │   ├── scoreboard.ts      # UI-14, UI-14a
│   │   ├── last_trick.ts      # UI-14b
│   │   └── banner.ts          # seat lost, stream broken, game over
│   └── util/
│       ├── dom.ts             # small element helpers
│       └── drag.ts            # drag-or-click gesture (UI-8)
└── dist/                      # tsc output; git-ignored
```

### 8.2 Build

ARC-8 forbids a bundler and any runtime dependency. `tsc` alone satisfies that:

```jsonc
// frontend/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "outDir": "dist",
    "rootDir": "src",
    "sourceMap": true
  },
  "include": ["src/**/*.ts"]
}
```

```jsonc
// frontend/package.json
{
  "name": "pinochle-frontend",
  "private": true,
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "watch": "tsc -p tsconfig.json --watch",
    "check": "tsc -p tsconfig.json --noEmit"
  },
  "devDependencies": { "typescript": "^5.6.0" }
}
```

The browser loads the output as native ES modules:

```html
<script type="module" src="/static/main.js"></script>
```

**The one gotcha this imposes:** because nothing rewrites the import specifiers,
every relative import in the TypeScript source must be written with a `.js`
extension — `import { render } from "./view/table.js";` — even though the file on
disk is `table.ts`. This is how `tsc` is meant to be used without a bundler, and
getting it wrong produces a 404 at run time rather than a compile error.

Node is a **build-time** tool only. §10.2's runtime image contains no Node, and a
developer who does not want npm at all can run `tsc` however they like, or commit
`dist/`, since the server serves whatever is in `PINOCHLE_FRONTEND_DIR`.

### 8.3 State: one reducer, one render

```ts
const state = initialState();
stream.on("card_played", e => { apply(state, e); render(state); });
```

`table_state.ts` exports a single `apply(state, envelope)` that folds one event
into the view state, and `table.ts` exports a single `render(state)`. There is
no virtual DOM and no framework; `render` is idempotent and cheap enough to run
on every event, because a Pinochle table is a few dozen elements.

The state the client holds is exactly what the events gave it: seats and names,
its own hand, cards on the table, exposed meld, the bid history, cumulative
scores, the previous trick, the current phase and turn from the `turn` header,
and any active pause. **It stores no derived rule state.** In particular:

- it does not compute legal plays — it uses `turn_prompt.legal_plays` (UI-9);
- it does not decide who won a trick — it waits for `trick_completed`;
- it does not tally card points during a round. UI-14c forbids showing a running
  total, and the reducer must not accumulate one even privately, so that the
  prohibition cannot be undone by a later change to a view module. Trick points
  enter the state for the first time with `round_scored` (FR-66).

### 8.4 Geometry and rendering

**Seating (UI-1).** Turn order is clockwise N → E → S → W, so the player who acts
after you sits to your left on screen. With `me` as the viewer's seat index:

```
bottom = me            left = (me + 1) % 4
across = (me + 2) % 4  right = (me + 3) % 4
```

**Hand order (FR-23, FR-23a).** `cards.ts` sorts by suit in the fixed order
Spades, Hearts, Diamonds, Clubs, and within a suit descending A, 10, K, Q, J, 9.
Once `trump_named` arrives, the trump suit moves to the leftmost position and the
other three keep their relative order — the only re-sort in a round, and it is
animated with a CSS transform transition so the cards visibly travel rather than
teleport.

**The trick area (UI-6).** Four absolutely-positioned slots offset toward each
seat, so all four cards are simultaneously visible and attributable. Cards remain
in place until `trick_cleared`, then animate toward the winner's seat.

**Card images (UI-16).** `<img src="/assets/cards/fronts/QS.svg">` for faces
and `/assets/cards/backs/blue.svg` for backs. These URLs refer directly to
files in `frontend/public/cards/`; no server-side card-image resolver is
involved. Opponents' hands are fanned backs with the correct remaining count,
which the client derives from cards played (UI-5).

**Table (UI-2, UI-17).** A fixed-size table element, centred and scaled to the
viewport with a single CSS `transform: scale()` driven by one resize listener.
Chrome and Firefox at desktop sizes are the target; the scaling approach does not
preclude smaller viewports later, but they are not tested.

### 8.5 Interaction

`drag.ts` implements the pair of gestures UI-8 requires — pointer-drag to the
table centre, and click, exactly equivalent — over the same set of eligible
elements, and is reused for both the trick play and the four-card pass. Elements
that are not currently legal get a class that dims them and are not registered as
drag sources, so the client "refuses to submit an illegal play" (UI-9) before the
server ever has to.

Bidding (UI-10) offers a stepper constrained to multiples of 10 at or above
`turn_prompt.minimum_bid`, plus Pass, plus the running bid history. Trump
(UI-11) offers the four suits. Passing (UI-12) requires exactly
`turn_prompt.count` selections before Confirm enables, and shows received cards
to the receiving team only — which needs no client-side check, since the
opposing team's stream never carries `cards_passed` at all.

The scoreboard (UI-14, UI-14a) is persistent: cumulative scores, the contract,
the auction winner, trump, the round's bid history, and each team's meld total,
the last of these surviving after the exposed meld leaves the table. The
last-trick view (UI-14b) keeps exactly one previous trick, replaced on each
`trick_cleared` — the client discards the one before it, so the courtesy cannot
be abused into a full history.

---

## 9. The administrator's role

The administrator is the person who stands the server up and turns four names
into a game in progress. They have no in-game powers: they cannot see a hand, act
for a seat, or alter a score. Their authority is entirely at the boundaries —
setup, and ending a game that cannot continue.

### 9.1 Standing up the server

1. Choose a host reachable by all human players and install Docker.
2. Set an admin token. Either put `PINOCHLE_ADMIN_TOKEN` in the compose file's
   environment, or omit it: the server then generates one at startup and writes
   it to the log, where `docker compose logs pinochle` will show it. A generated
   token changes on every restart, which is fine for a one-evening game.
3. Set `PINOCHLE_PUBLIC_BASE_URL` to the URL players will actually type
   (`https://pinochle.example`). Join links are built from it, so if it is wrong
   the links will point somewhere unreachable.
4. `docker compose up -d`, then confirm `GET /healthz` returns `{"status":"ok"}`.

Because state is in memory (NFR-8) and the process is single-worker (§4.7),
restarting the container destroys any game in progress. The administrator should
treat "the server is up" and "the game has started" as the same commitment.

### 9.2 Creating the game

The administrator opens `/admin` and pastes the admin token, which the console
holds in `sessionStorage` and sends as `X-Admin-Token`. It is never written to
`localStorage` and never appears in a URL.

They then fill in one form (FR-7):

- a name for each of the four seats, North, East, South, and West;
- for each seat, human or computer — freely mixable, including all four of either
  (FR-2);
- a display name for each partnership. The team *identifiers* NS and EW are fixed
  by the seating and are not offered as choices (FR-4a).

Submitting calls `POST /api/admin/games` (§5.2). The response is the game id and
a **join link for each human seat** (FR-10):

```
https://pinochle.example/join/5c1f7b2e…?t=8Qk3vRz9Xp2LmN…
```

The console displays these with a copy button each, and one warning it should
state plainly: **a join link is a credential.** It is the sole thing that
authorises that seat (FR-10a) — anyone holding it can see that hand and play
those cards. The administrator distributes them one to one, by whatever private
channel they already use, and does not paste them into a shared channel. The
tokens are shown exactly once; there is no way to retrieve them later, and no way
to re-issue one without creating a new game.

If the administrator is also playing (FR-8), they take their own seat's link and
open it in an ordinary tab. The admin console and the player view are separate
pages with separate credentials; nothing about being the administrator changes
what their seat can see.

### 9.3 Waiting for the table to fill

The console keeps its own SSE stream (`GET /api/admin/games/{id}/stream`, §5.2),
which carries public events plus `seat_lost` / `seat_rejoined`. Before the game
starts, this is a join board: each human seat shows *waiting* until a stream
opens for it, then *joined*.

The Start button stays disabled until all four seats are accounted for —
computer seats are ready immediately, human seats when they have joined. This is
FR-10b, and the server enforces it too: `POST …/start` returns
`409 setup_incomplete` if a human seat has no open stream, so a stale console
cannot start a game that half the table would miss.

### 9.4 Starting play

Pressing Start calls `POST /api/admin/games/{id}/start`, which validates the
seating (FR-9) and moves the game into `DEALER_SELECTION`. From that moment the
game runs itself:

- all four clients receive `dealer_selection_started` and render the 48 face-down
  positions; each player clicks one, and computer seats draw at random through
  the same endpoint (FR-11a, FR-11b);
- ties reshuffle and repeat automatically (FR-14);
- the dealer is announced, the first round is dealt, and play proceeds.

The administrator does nothing further. There is no "next round" button, no
scoring confirmation, and no timer to manage: the two waits that hold the game
open, the lone bidder's decision and the meld display, wait on a player, and the
two timed pauses are counted by the server (§6.7).

### 9.5 During the game

The console shows public state only: phase, whose turn it is, the bid history,
cumulative scores, and the connection status of each seat. It cannot show a hand,
because every private event goes out through `notify` and the admin queues are
subscribed only to `broadcast` (§6.3) — the restriction is structural, not a rule
the console is trusted to follow.

The one situation demanding a decision is a lost seat. If a human player closes
their last tab or loses their network, the hub broadcasts `seat_lost`, every
client shows a banner naming that seat, and play stops there permanently: nothing
substitutes for a human seat (FR-2a), and the player cannot rejoin (RT-5, RT-12).
The administrator's choice is then simply when to declare it over. `Abandon`
(`POST …/abandon` with a reason) broadcasts `game_abandoned`, revokes the tokens,
and lets everyone close the tab knowing why, rather than waiting on a seat that
will never act. Starting again means creating a new game and distributing new
links; there is nothing to resume.

### 9.6 Tuning

Two knobs affect the feel of a game and are set on the container, not per game
(§10.4): `PINOCHLE_TRICK_CLEAR_SECONDS`, how long a completed trick stays on the
table (UI-15), and `PINOCHLE_COMPUTER_DELAY_SECONDS`, how long a computer seat
appears to think (FR-75c). Setting the latter to `0` makes an all-computer game
run at full speed, which is useful for demonstrating or exercising the server.

---

## 10. Docker

### 10.1 What the image contains

One image runs the whole system: the FastAPI server and the compiled front end,
including its card artwork. There is no database (NFR-8) and no second service,
so there is nothing to orchestrate beyond one container.

It is built in two stages. The first uses Node solely to run `tsc`; the second is
a slim Python runtime that receives the compiled JavaScript. **No Node, no npm,
and no TypeScript source ship in the runtime image** — which is exactly ARC-8's
"no bundler or runtime dependency shall be required to run it", made literal.

### 10.2 `docker/Dockerfile`

```dockerfile
# ---------- stage 1: compile the TypeScript front end ----------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY frontend/tsconfig.json ./
COPY frontend/src ./src
RUN npm run build          # → /build/dist

# ---------- stage 2: the runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PINOCHLE_FRONTEND_DIR=/app/frontend

WORKDIR /app

# Dependencies first, so a code change does not re-resolve them.
COPY pyproject.toml README.md ./
COPY pinochle ./pinochle
RUN pip install --no-cache-dir .        # NFR-2: plain install is sufficient

# The front end: hand-written assets, plus the compiled output.
COPY frontend/public ./frontend/public
COPY --from=frontend /build/dist ./frontend/dist

RUN useradd --system --uid 10001 --create-home pinochle
USER pinochle

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2).status==200 else 1)"

# --workers 1 is mandatory, not a default: see §4.7.
CMD ["uvicorn", "pinochle.web.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--timeout-keep-alive", "75", "--no-access-log"]
```

Notes on the choices:

- `--workers 1` is load-bearing. A second worker would hold a second, empty
  `InMemoryGameState` and a second SSE hub (§4.7).
- `--timeout-keep-alive 75` comfortably exceeds the 15-second keepalive interval,
  so an idle stream is never closed by the server itself.
- `--no-access-log` is set because the SSE URL carries a seat token in its query
  string (§6.2); the application's own structured log (§4.9) is the audit trail,
  and it does not record tokens.
- The health check uses `urllib` rather than adding `curl` to the image.
- `pip install .` with no extras is enough, once §12's dependency move is done.

### 10.3 `docker/compose.yaml`

```yaml
services:
  pinochle:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    image: pinochle:latest
    container_name: pinochle
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      PINOCHLE_ADMIN_TOKEN: "${PINOCHLE_ADMIN_TOKEN:-}"
      PINOCHLE_PUBLIC_BASE_URL: "${PINOCHLE_PUBLIC_BASE_URL:-http://localhost:8000}"
      PINOCHLE_TRICK_CLEAR_SECONDS: "1.5"
      PINOCHLE_COMPUTER_DELAY_SECONDS: "1.0"
      PINOCHLE_LOG_LEVEL: "INFO"
      PINOCHLE_SSE_KEEPALIVE_SECONDS: "15"
      PINOCHLE_SSE_QUEUE_MAXSIZE: "256"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2)"]
      interval: 30s
      timeout: 3s
      retries: 3
```

No volume is mounted: there is nothing to persist (NFR-8). `restart:
unless-stopped` keeps the server available across a host reboot, with the
understanding that any game in flight is lost.

A development override can bind-mount the source and add `--reload`, but note
that a reload drops every SSE connection and therefore every seat.

### 10.4 Configuration

| Variable | Default | Effect | Requirement |
| --- | --- | --- | --- |
| `PINOCHLE_ADMIN_TOKEN` | generated at startup and logged | Credential for `/api/admin/*` | FR-6 |
| `PINOCHLE_PUBLIC_BASE_URL` | `http://localhost:8000` | Host part of the join links | FR-10 |
| `PINOCHLE_TRICK_CLEAR_SECONDS` | `1.5` | Trick-clear pause | UI-15 |
| `PINOCHLE_COMPUTER_DELAY_SECONDS` | `1.0` | Computer thinking delay; `0` disables | FR-75c, RT-7 |
| `PINOCHLE_LOG_LEVEL` | `INFO` | Enables the action/event log without a code change | NFR-9 |
| `PINOCHLE_SSE_KEEPALIVE_SECONDS` | `15` | Comment-frame interval | §6.8 |
| `PINOCHLE_SSE_QUEUE_MAXSIZE` | `256` | Per-connection buffer before the stream is dropped | §6.8 |
| `PINOCHLE_FRONTEND_DIR` | `frontend` | Where `public/` and `dist/` are found | §3 |
| `PINOCHLE_SHUFFLE_SEED` | unset | Seeds the shuffle for reproducible deals | NFR-7 |

### 10.5 Behind a reverse proxy

SSE is the one thing a default proxy configuration reliably breaks, by buffering
the response until it is "complete" — which, for a stream, is never. The server
sets `X-Accel-Buffering: no` on the stream response, which nginx honours, but the
proxy also needs:

```nginx
location /api/ {
    proxy_pass              http://pinochle:8000;
    proxy_http_version      1.1;
    proxy_set_header        Connection "";     # keep-alive to the upstream
    proxy_buffering         off;               # essential for SSE
    proxy_cache             off;
    proxy_read_timeout      1h;                # a table can idle for a long time
}
```

Two further points: the proxy must not compress `text/event-stream` (buffering
again), and its access-log format should omit or strip the `t` query parameter,
which carries a seat token (§6.2).

### 10.6 Running it

```
docker compose -f docker/compose.yaml up -d --build
docker compose -f docker/compose.yaml logs -f pinochle    # admin token, events
docker compose -f docker/compose.yaml down
```

The log is the operational surface. It carries the generated admin token at
startup and, at `INFO`, every accepted action, every rejection with its reason,
and every published event — but no hands and no tokens (NFR-9).

---

## 11. Testing

The existing suite covers the domain thoroughly and runs without a server or a
browser (NFR-3). The design extends it in four directions.

**Domain and services** — unchanged in kind. New event emissions get assertions
in the existing service tests.

**The scheduler seam (ARC-10).** `FakeScheduler` holds callbacks against a
virtual clock. A test of the trick-clear pause plays four cards, asserts that a
fifth is rejected with `wrong_phase` (RT-9), calls `advance(1.5)`, and asserts
`trick_cleared` was published. No test sleeps.

**The SSE adapter and encoder.** Subscribe two queues to one seat and assert both
receive a `notify` (FR-10c). Assert a `broadcast` reaches the admin queue and a
`notify` does not (§6.3). Assert the encoder escapes newlines, emits monotonic
ids, and produces a frame `EventSource` would accept.

**The web layer.** `httpx.ASGITransport` against `create_app(test_container)`.
Endpoint tests assert the status-code mapping of §5.5 and that a rejected action
left the game unchanged (NFR-4). One stream test opens the SSE response, drives
the game through the fake scheduler, and asserts the exact frame sequence for a
trick — which is where §6.7's bracketing pairs are pinned down.

**End to end.** One test creates an all-computer game with
`computer_delay_seconds=0` and a seeded shuffle, drives it to `game_over` through
the fake clock, and asserts a plausible final score. It is fast, deterministic,
and exercises every phase including toss-in and abandonment, given the right
seeds.

**Privacy.** The frame-level assertion described in §6.6, which is the one test
that would catch a regression in NFR-6 no matter where it was introduced.

**Front end.** `npm run check` (`tsc --noEmit`) is the whole front-end test
suite. Types in `model/events.ts` mirror §6.5, so a change to an event payload
that the client does not follow becomes a compile error.

---

## 12. Dependencies

`pyproject.toml` needs two changes.

First, the runtime dependencies:

```toml
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "pytest",
    "pytest-mock",
    "pytest-asyncio",
    "httpx",
]
```

Second, `[project.optional-dependencies]` is removed. NFR-2 requires that
`pip install -e .` alone be sufficient to run the tests, so pytest and the rest
belong in `[project.dependencies]` — the same rule the Dockerfile relies on in
§10.2.

No SSE library is needed: Starlette's `StreamingResponse` over an async generator
is the whole implementation, and `sse-starlette` would add a dependency for
something that is a dozen lines. The front end has no runtime dependency at all;
`typescript` is a build-time devDependency (§8.2).

---

## 13. Suggested build order

Each step leaves the suite green and the system demonstrable.

1. **Domain events.** Add the events of §4.1 and enrich `RoundScored` and
   `GameOver`; emit them from `GameService`. Pure domain work, fully unit-tested.
2. **Errors.** Introduce `PinochleError` and its subclasses, and replace the bare
   `ValueError`s in `Round` and `GameService`.
3. **Scheduler adapters.** `AsyncioScheduler` and `FakeScheduler`; convert the
   trick-clear test to the fake clock.
4. **Seat tokens.** `SeatTokenPort` and `InMemorySeatTokens`.
5. **Notification adapters.** `SseNotification`, `LoggingNotification`,
   `CompositeNotification`, and the frame encoder.
6. **The web layer.** Container, dependencies, error handler, admin router,
   player router, and stream router; `httpx` tests throughout.
7. **The computer driver.** `ComputerDriver`, `SeatView`, the pump, and the
   strategy improvements for FR-75a and FR-75b. At the end of this step an
   all-computer game runs end to end over HTTP with no browser.
8. **The front end.** `frontend/` skeleton, the event types, the reducer, then
   the views in playing order: table and seats, dealer-selection spread, hand,
   bidding, trump, passing, meld, trick, scoreboard, banners.
9. **Docker.** The two-stage image and compose file; verify SSE through a proxy.
10. **Polish.** Animations for the trump re-sort (FR-23a) and the trick sweep,
    the last-trick view (UI-14b), and the admin console's join board.

Steps 1–7 are testable without a browser, and step 7 ends with a complete,
exercisable server. That ordering is deliberate: the front end is written against
a system that already works.

---

## 14. Design decisions and assumptions

**14.1 FR-10c and RT-5 pull in opposite directions.** FR-10c permits a seat
several concurrent connections, all showing the same view. RT-5 forbids the
server from reconstructing a view for a client that does not already have one.
Both can hold only when every connection for a seat is opened before the deal —
which FR-10b makes the normal case. A tab opened mid-game is therefore accepted,
authorised, and fed every subsequent event, but it cannot show a table; it
displays "joined mid-game" instead (§6.9). The design deliberately does *not*
keep a per-seat event journal, because replaying one would let a dropped client
rebuild, which RT-5 explicitly denies. Should that requirement ever be relaxed, a
journal is a small change confined to `SseNotification` and would make both
mid-game tabs and true reconnection work; nothing else in the design would move.

**14.2 The turn header and `turn_prompt` are additions.** The requirements list
the events to be published (RT-4) but not how a client learns whose turn it is or
which cards are legal. Deriving either on the client would violate ARC-2, so the
server states both: public turn and phase on every frame, private options to the
acting seat (§6.4, §6.5).

**14.3 `seat_lost`, `seat_rejoined`, and `game_abandoned` are transport-level
events.** RT-12 requires the other players be told a seat is gone, but the domain
knows nothing about connections and should not. These three are published by the
hub and the admin router, not by `Game`, and they are the only events in §6.5
that do not originate in the domain.

**14.4 The admin's abandon action is inferred.** RT-12 says the remaining players
should abandon the game deliberately rather than wait; it does not say who ends
it. Giving the administrator an explicit action, and everyone else a clear
announcement, seemed the smallest thing that satisfies the intent.

**14.5 The seat token travels in the SSE query string.** `EventSource` cannot set
headers, and FR-10a makes the token the sole credential, so there is no second
mechanism to fall back on. §6.2 and §10.5 describe the mitigations. A cookie set
at join time would keep it out of URLs, at the cost of introducing a credential
that is not the token; the design chose to keep FR-10a literal.

**14.6 One process, one worker.** NFR-5 allows one game at a time and NFR-8 keeps
state in memory, so the design commits to a single event loop in a single worker
and takes the simplicity that buys: no locks, no serialisation, atomic
domain-operation-and-dispatch cycles. It is recorded here because it is
invisible in the code and fatal to violate.

**14.7 Front-end ownership supersedes the card-image portion of ARC-5.** ARC-5
currently names card image resolution as a driven server port. This design no
longer includes that port: immutable artwork used only for presentation lives in
`frontend/public/cards/` and is resolved by static browser URLs. ARC-5 must be
amended to remove card image resolution when the requirements are next updated.
