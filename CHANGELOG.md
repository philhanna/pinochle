# Change log for pinochle
All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning].
The format is based on [Keep a Changelog].

## [Unreleased]

### Added
- `docs/impl.md`: the sliced implementation plan for the remaining work (the
  front end), with a review point and a manual check per slice, the decisions
  locked before coding starts, and the single-desktop verification workflow
- `Makefile`, `scripts/dev.sh`, `scripts/seed.py`: the development loop
  (impl.md slice A0). `make dev` runs the server on localhost with a fixed
  admin token; `make seed` creates a game, prints the join links, and starts it
  once the human seats have opened their streams (FR-10b); `make seed-watch`
  runs an all-computer table
- `frontend/`: the browser client's own tree — TypeScript compiled by `tsc` to
  ES modules the browser loads directly, with no bundler and no runtime
  dependency (ARC-8). Phase A's page is a raw event log: the wire contract is
  reviewable before any presentation code exists. The seat token is held in the
  URL and `sessionStorage`, never `localStorage`, so four seats can be four
  tabs of one browser
- The administrator's console (impl.md slice A2): create a game with four
  named seats, copy each human seat's join link, see which seats have joined,
  start the game, abandon it, and watch the public event stream live. An
  all-computer table issues no join links, so the console's stream view is the
  only way to watch one
- The table itself (impl.md slices C1-C6): a green felt surface with the
  viewing player's seat at the bottom, the partner across and the opponents to
  either side (UI-1, UI-2); the partnerships distinguished and the acting seat
  marked (UI-3, UI-7); this seat's hand face-up and fanned in the order of
  FR-23, the other three as fans of backs at their true size (UI-4, UI-5); the
  trick with each card nearer the seat that played it (UI-6); the last
  completed trick on demand (UI-14b); a persistent scoreboard carrying the
  contract, the auction winner, trump, the bid history and each team's meld
  total for the whole round (UI-14, UI-14a); exposed meld per seat and per team
  (UI-13); the round summary and the game-over panel (FR-66, FR-71)
- Card input by drag or by click, the two being exactly equivalent (UI-8).
  Legal cards are distinguished from illegal ones and an illegal one cannot be
  submitted (UI-9) — legality is whatever the server's turn prompt listed, and
  no rule is decided in the browser (ARC-2)
- Controls for every phase a seat acts in: bid entry constrained to multiples of
  ten at or above the minimum, or pass (UI-10); accept or decline a lone
  bidder's contract (FR-32); the trump picker (UI-11); choose exactly four cards
  and confirm the pass, with the received cards shown to the receiving team only
  (UI-12); play the contract out or toss it in (FR-50a, FR-50b)
- The face-down dealer-selection spread, drawn from by clicking a position
  (FR-11, FR-11a)
- `frontend/src/state.ts`: the client's whole model of the game (impl.md slice
  B1). RT-5 puts no snapshot on the server, so this reducer is not a cache of
  something authoritative elsewhere — it is the only model the browser has.
  Pure `applyEvent(state, frame)`, no DOM, 47 tests under `node --test`
- `frontend/src/cards.ts`: card codes, and the hand order of FR-23/FR-23a —
  grouped by suit, descending by rank with the ten above the king, trump moving
  leftmost once it is named
- `scripts/record_frames.py` and `make record`: record one seat's event stream
  from an all-computer game as the reducer's test fixture, through the real
  service and the real encoder so it cannot drift from the wire format
- `make test` now runs the client tests as well as the server's, with
  `make test-py` and `make test-fe` for one at a time
- `pinochle/web/routers/cards.py`: card artwork over HTTP (UI-16), addressed by
  the same two-character wire code the event stream uses — `/cards/faces/TS`
  for the ten of spades, `/cards/backs/blue` for a back, either in SVG or PNG,
  cached immutably. Previously `CardImagePort` could resolve artwork on disk but
  nothing served it
- `CardImagePort` in the container's object graph, wired to `SvgCardImage`

### Changed
- `docker/Dockerfile` is now a two-stage build: a Node stage compiles
  `frontend/src`, and the Python runtime image copies the result. The client is
  compiled in the image rather than copied from the host, so the image can never
  serve a stale `frontend/dist`
- A missing front-end page now names the file and suggests `make build`, rather
  than reporting that the front end does not exist
- FR-75a now states that a computer player's bid valuation is a *partnership*
  valuation — its own meld, the trick points both hands together can take, and
  an allowance for the partner's contribution — rather than a valuation of its
  own hand alone, which no hand could ever bid on

### Security
- The administrator's SSE endpoint now accepts its token as `?t=` as well as in
  the `X-Admin-Token` header, because `EventSource` cannot set headers. It sits
  on a router of its own so that only this read-only route accepts a token that
  way: every command that changes a game still requires the header, so a
  forwarded URL cannot create, start or abandon a game

### Fixed
- The client offered a card during the trick-clear pause, which the server
  rejects as out-of-phase (RT-9): a pause is a state the game occupies, not a
  presentation effect, so no play is offered while one runs
- A seeded game was not reproducible (NFR-7). The computers' dealer-selection
  draw used the unseeded global `random`, and the driver scheduled the waiting
  seats straight from a `set`, whose iteration order depends on string hashing
  and differs between processes. The draw picks the dealer and the dealer
  decides which twelve cards of the shuffle each seat receives, so a seeded
  shuffle alone reproduced nothing. `ComputerPlayerStrategy` now takes the
  game's own `Random`, and the driver walks the waiting seats by seat position
- A request for artwork that is well-formed but absent from disk is now a 404
  rather than an unhandled `FileNotFoundError` and a 500
- The computer player now bids. It valued a hand as its own meld plus a trick
  estimate from its own twelve cards, but a contract is scored against the
  partnership, so the valuation could not reach the 250 minimum (FR-27) and the
  strategy passed unconditionally: an all-computer game abandoned 302 of 309
  rounds under FR-31 and took 212 rounds to finish. `choose_bid` now adds
  `_PARTNER_CONTRIBUTION`, a flat allowance of 180 for what the partner brings,
  which over 16 complete games cuts a game to 13.4 rounds, with a tenth of them
  abandoned and the bidding side making its contract 64% of the time. The
  allowance is a single figure meant to be tuned by playing games

## [0.3.0] - 2026-09-07

### Added
- `pinochle/domain/errors.py`: the `PinochleError` hierarchy
  (`UnknownGameError`, `NotYourTurnError`, `WrongPhaseError`,
  `IllegalActionError`, `SetupError`), replacing bare `ValueError`/`KeyError`
  across the domain and service layers
- `pinochle/adapters/`: `AsyncioScheduler` and `FakeScheduler` (a
  virtual-clock `SchedulerPort`, so tests never wait in real time for a
  pause to elapse), `InMemorySeatTokens`, `SseNotification`,
  `LoggingNotification`, `CompositeNotification`
- `pinochle/ports/seat_token_port.py`: `SeatTokenPort`, the per-seat
  credential a join link carries
- `pinochle/web/`: a full FastAPI + Server-Sent Events layer — admin,
  player, and stream routers; seat and admin token authentication; a
  `PinochleError`-to-HTTP-status mapping; the `card_codec`/`event_encoder`/
  `turn_header` wire format; a `TurnPrompt` event, so a client is told what
  is legal rather than deriving it
- `pinochle/services/computer_driver.py`: `ComputerDriver`, driving every
  computer seat through the same ports a human client uses;
  `pinochle/services/seat_view.py`: `SeatView`, the private slice of state a
  strategy is allowed to see
- Bidding (`choose_bid`) and passing heuristics in `ComputerPlayerStrategy`,
  replacing the placeholder that always passed the four lowest cards
- `docker/Dockerfile`, `docker/compose.yaml`, `.dockerignore`: a
  backend-only container image — the browser front end is a later addition
- Seedable shuffling end to end (`Deck.shuffle`, `Round.deal`,
  `GameService`'s `rng` parameter)
- 277 unit and integration tests, including an all-computer game driven to
  `game_over` with no browser, over both a bare service and the full
  production container

### Changed
- `BidPlaced` now carries `current_high`; `TrickCompleted` carries
  `(player_id, card)` pairs instead of bare cards, so the wire format never
  has to re-derive who played what
- `GameService` takes `trick_clear_seconds` and `rng` as constructor
  arguments instead of a module constant and the global `random` module
- Moved `pytest-asyncio`, `fastapi`, `uvicorn[standard]`, and `httpx` into
  `[project.dependencies]`

### Fixed
- The `pinochle` logger tree was never configured, so the action/event
  audit log never reached `docker compose logs`; a generated admin token
  was never logged either — both now happen at startup

## [0.2.0] - 2026-09-06

### Added
- Hexagonal (ports and adapters) architecture
- `pinochle/domain/`: pure game logic — `Rank`, `Suit`, `Card`, `Deck`,
  `Player`, `Team`, `Hand`, `BiddingRound`, `detect_meld`, `Trick`,
  `scoring`, `Game` aggregate root with domain events
- `pinochle/ports/`: `AdminPort`, `PlayerActionPort` (inbound);
  `GameStatePort`, `NotificationPort`, `CardImagePort` (outbound)
- `pinochle/adapters/`: `InMemoryGameState`, `PrintNotification`,
  `SvgCardImage`
- `pinochle/services/`: `GameService` use-case layer and the `Round`
  state machine that orchestrates a single round
- `pinochle/strategies/`: `ComputerPlayerStrategy` (rule-based AI)
- `pinochle/app.py`: `create_default_app()` wiring entry point
- Full domain event stream, so a client can render the table from the
  events alone: `GameConfigured`, `DealerSelectionStarted`, `DrawMade`,
  `DrawTied`, `RoundStarted`, `ContractOffered`, `PlayBegun`,
  `SeatThinking`, `CardPlayed`, `TrickCleared`
- `TeamRoundScore`, carrying a team's whole round arithmetic (meld, card
  points, last-trick bonus, round total, points applied, cumulative)
  rather than a single figure
- `docs/requirements.md`: the settled specification, with §10 as the
  decision record
- `docs/design.md`: how the requirements will be built
- `docs/docker-usage.md`: Docker and VPS deployment guide
- Detailed docstrings across every class and module
- `pyproject.toml`: package metadata and pytest configuration
- 170 unit tests across `tests/domain/`, `tests/ports/`,
  `tests/adapters/`, `tests/services/` and `tests/strategies/`

### Changed
- Dealer selection draws from one shared face-down spread, replaced
  wholesale on a tie, instead of per-player draws
- The auction winner ends the meld display, or tosses the contract in
- The server is the sole owner of all game timers
- Renamed the `cards` package to `card_images` and cleaned up its layout
- Simplified the ports and adapters directory structure
- Moved pytest and pytest-mock into `[project.dependencies]`, so
  `pip install -e .` alone is enough

### Fixed
- Meld marriages, dealer rotation, and team derivation
- Turn-order enforcement and the must-beat rule
- Meld capture, the meld hold, and event privacy

### Removed
- Seat substitution, deferred past the first release
- Reconnection, deferred past the first release
- The computer strategy, deferred past the first release
- The unused `players` package
- Superseded design documents

## [0.1.0] - 2026-03-27
Beginning of ports and adapters version

## [0.0.0] - 2023-07-19
Start of Go version

[Semantic Versioning]: http://semver.org
[Keep a Changelog]: http://keepachangelog.com
[Unreleased]: https://github.com/philhanna/pinochle/compare/0.2.0..HEAD
[0.2.0]: https://github.com/philhanna/pinochle/compare/0.1.0..0.2.0
[0.1.0]: https://github.com/philhanna/pinochle/compare/0.0.0..0.1.0
[0.0.0]: https://github.com/philhanna/pinochle/compare/b4aba0b..0.0.0
