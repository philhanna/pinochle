# Change log for pinochle
All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning].
The format is based on [Keep a Changelog].
	
## [Unreleased]

### Added
- Hexagonal (ports and adapters) architecture
- `pinochle/domain/`: pure game logic — `Rank`, `Suit`, `Card`, `Deck`,
  `Player`, `Team`, `Hand`, `BiddingRound`, `detect_meld`, `Trick`,
  `scoring`, `Round` state machine, `Game` aggregate root with domain events
- `pinochle/ports/`: `AdminPort`, `PlayerActionPort` (inbound);
  `GameStatePort`, `NotificationPort`, `CardImagePort` (outbound)
- `pinochle/adapters/`: `InMemoryGameState`, `PrintNotification`,
  `SvgCardImage`, `ComputerPlayerAdapter` (rule-based AI)
- `pinochle/app.py`: `create_default_app()` wiring entry point
- `pyproject.toml`: package metadata and pytest configuration
- 84 unit tests across `tests/domain/`, `tests/ports/`, `tests/adapters/`

## [0.0.0] - 2023-07-19
Start of Go version

[Semantic Versioning]: http://semver.org
[Keep a Changelog]: http://keepachangelog.com
[Unreleased]: https://github.com/philhanna/pinochle/compare/0.0.0..HEAD
[0.0.0]: https://github.com/philhanna/pinochle/compare/b4aba0b..0.0.0
