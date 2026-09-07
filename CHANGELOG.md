# Change log for pinochle
All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning].
The format is based on [Keep a Changelog].

## [Unreleased]

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
