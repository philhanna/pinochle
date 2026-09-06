# Change log for pinochle
All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning].
The format is based on [Keep a Changelog].

## [Unreleased]

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
