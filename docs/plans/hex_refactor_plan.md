# Hexagonal Architecture Refactor Plan

## Overview

This document describes the plan for refactoring the pinochle project to the **Ports and Adapters** (hexagonal) architecture. The goal is to isolate the pure game domain from delivery mechanisms (HTTP/WebSocket, CLI) and infrastructure (persistence, external services), making it easy to test, swap, and extend each layer independently.

---

## Implemented Structure

```
pinochle/                          # top-level package
│
├── domain/                        # Pure game logic — no I/O, no frameworks
│   ├── __init__.py
│   ├── cards/
│   │   ├── __init__.py            # re-exports Card, Rank, Suit, Deck
│   │   ├── rank.py                # Rank enum
│   │   ├── suit.py                # Suit enum (_is_windows private helper)
│   │   ├── card.py                # Card class
│   │   └── deck.py                # 48-card Pinochle deck
│   ├── bid.py                     # BiddingRound state machine + validation
│   ├── game.py                    # Game aggregate root + domain events
│   ├── hand.py                    # Hand with legal-play rules
│   ├── meld.py                    # detect_meld() — all 15 meld types
│   ├── player.py                  # Player dataclass, PlayerType, Position enums
│   ├── round.py                   # Round state machine
│   ├── scoring.py                 # score_tricks(), resolve_round()
│   ├── team.py                    # Team dataclass
│   └── trick.py                   # Trick with trump/lead-suit winner logic
│
├── ports/                         # Interfaces / contracts (flat — no subdirs)
│   ├── __init__.py
│   ├── admin_port.py              # AdminPort ABC — game setup commands
│   ├── card_image_port.py         # CardImagePort ABC — resolve card image assets
│   ├── game_state_port.py         # GameStatePort ABC — load/save game state
│   ├── notification_port.py       # NotificationPort ABC — push events to players
│   └── player_action_port.py      # PlayerActionPort ABC — player moves
│
├── adapters/                      # Concrete implementations (flat — no subdirs)
│   ├── __init__.py
│   ├── in_memory_game_state.py    # GameStatePort — dict-backed store
│   ├── print_notification.py      # NotificationPort — logs events to stdout
│   └── svg_card_image.py          # CardImagePort — resolves bundled SVG/PNG assets
│
├── services/                      # Use-case / application layer
│   ├── __init__.py
│   └── game_service.py            # GameService — implements AdminPort + PlayerActionPort
│
├── strategies/                    # AI / rule-based decision logic
│   ├── __init__.py
│   └── computer_player_strategy.py  # ComputerPlayerStrategy — stateless AI helpers
│
├── cards/
│   └── resources/                 # SVG/PNG card images (unchanged)
│       └── svg_playing_cards/
│           ├── fronts/
│           ├── backs/
│           └── other/
│
└── app.py                         # create_default_app() — wires adapters to ports

tests/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── test_bid.py
│   ├── test_card.py
│   ├── test_deck.py
│   ├── test_meld.py
│   ├── test_rank.py
│   ├── test_scoring.py
│   ├── test_suit.py
│   └── test_trick.py
├── ports/
│   ├── __init__.py
│   ├── test_card_image_port.py    # contract tests (run_contract helpers)
│   ├── test_game_state_port.py
│   └── test_notification_port.py
├── adapters/
│   ├── __init__.py
│   ├── test_in_memory_game_state.py
│   ├── test_print_notification.py
│   └── test_svg_card_image.py
├── services/
│   ├── __init__.py
│   └── test_game_service.py
└── strategies/
    ├── __init__.py
    └── test_computer_player_strategy.py
```

---

## Target Architecture

The hexagonal architecture organizes code into three concentric zones:

```
┌────────────────────────────────────────────────────────┐
│  Adapters (Infrastructure & Delivery)                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Ports (Interfaces / Contracts)                  │  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │  Domain (Pure Game Logic)                  │  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

- **Domain**: Python classes and functions with zero I/O and zero framework imports.
- **Ports**: Abstract base classes (ABCs) that define what the domain needs from the outside world (outbound) and what the outside world can ask of the domain (inbound).
- **Adapters**: Concrete implementations of ports — HTTP handlers, WebSocket clients, in-memory stores, computer-player AI, SVG renderers, etc.

---

## Ports (Interfaces)

### `AdminPort` (`ports/admin_port.py`)

```python
from abc import ABC, abstractmethod
from pinochle.domain.player import Player
from pinochle.domain.team import Team

class AdminPort(ABC):
    @abstractmethod
    def create_game(self) -> str: ...

    @abstractmethod
    def add_player(self, game_id: str, player: Player) -> None: ...

    @abstractmethod
    def assign_teams(self, game_id: str, ns: Team, ew: Team) -> None: ...

    @abstractmethod
    def start_game(self, game_id: str) -> None: ...
```

### `PlayerActionPort` (`ports/player_action_port.py`)

```python
from abc import ABC, abstractmethod
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit

class PlayerActionPort(ABC):
    @abstractmethod
    def draw_for_deal(self, game_id: str, player_id: str) -> Card: ...

    @abstractmethod
    def place_bid(self, game_id: str, player_id: str, amount: int | None) -> None: ...

    @abstractmethod
    def name_trump(self, game_id: str, player_id: str, suit: Suit) -> None: ...

    @abstractmethod
    def pass_cards(self, game_id: str, player_id: str, cards: list[Card]) -> None: ...

    @abstractmethod
    def play_card(self, game_id: str, player_id: str, card: Card) -> None: ...
```

### `GameStatePort` (`ports/game_state_port.py`)

```python
from abc import ABC, abstractmethod
from pinochle.domain.game import Game

class GameStatePort(ABC):
    @abstractmethod
    def save(self, game: Game) -> None: ...

    @abstractmethod
    def load(self, game_id: str) -> Game: ...

    @abstractmethod
    def delete(self, game_id: str) -> None: ...
```

### `NotificationPort` (`ports/notification_port.py`)

```python
from abc import ABC, abstractmethod
from pinochle.domain.game import GameEvent

class NotificationPort(ABC):
    @abstractmethod
    def notify(self, player_id: str, event: GameEvent) -> None: ...

    @abstractmethod
    def broadcast(self, game_id: str, event: GameEvent) -> None: ...
```

### `CardImagePort` (`ports/card_image_port.py`)

```python
from abc import ABC, abstractmethod
from pinochle.domain.cards.card import Card

class CardImagePort(ABC):
    @abstractmethod
    def get_image_path(self, card: Card, fmt: str = "svg") -> str: ...

    @abstractmethod
    def get_back_path(self, fmt: str = "svg") -> str: ...
```

---

## Adapters (Concrete Implementations)

| Adapter | Port | Status |
|---|---|---|
| `InMemoryGameState` | `GameStatePort` | ✅ implemented |
| `PrintNotification` | `NotificationPort` | ✅ implemented (stdout, dev only) |
| `SvgCardImage` | `CardImagePort` | ✅ implemented |
| `HttpAdminAdapter` | `AdminPort` | ⬜ not yet implemented |
| `HttpPlayerAdapter` | `PlayerActionPort` | ⬜ not yet implemented |
| `WebSocketNotification` | `NotificationPort` | ⬜ not yet implemented |

## Services (Use-Case Layer)

| Service | Implements | Status |
|---|---|---|
| `GameService` | `AdminPort` + `PlayerActionPort` | ✅ implemented |

`GameService` lives in `pinochle/services/` and acts as the single orchestrator for game setup and player moves. It depends on `GameStatePort` and `NotificationPort` (injected), and delegates AI decisions to `ComputerPlayerStrategy`.

## Strategies (AI / Rule-Based Logic)

| Strategy | Purpose | Status |
|---|---|---|
| `ComputerPlayerStrategy` | Stateless AI helpers (trump, passing, playing) | ✅ implemented |

`ComputerPlayerStrategy` is **not** an adapter — it does not implement a port. It lives in `pinochle/strategies/` and provides three static methods: `choose_trump()`, `choose_cards_to_pass()`, `choose_play()`. Callers (e.g. a CLI or WebSocket handler) use it alongside `PlayerActionPort` to submit the chosen moves.

---

## Domain Events

The `Game` aggregate root emits events that the `NotificationPort` broadcasts to players.
Defined as plain dataclasses in `pinochle/domain/game.py`:

- `DealerSelected`
- `CardsDealt`
- `BidPlaced`
- `TrumpNamed`
- `TrickCompleted`
- `RoundScored`
- `GameOver`

---

## Migration Steps

### Phase 1 — Restructure the cards module ✅

1. Created `pinochle/domain/` and `pinochle/domain/cards/`.
2. Moved `rank.py`, `suit.py`, `card.py` into `pinochle/domain/cards/`.
3. Removed `IS_WINDOWS()` from `cards/__init__.py`; made private `_is_windows()` in `suit.py`.
4. Added `deck.py` (48-card Pinochle deck).
5. Moved tests to `tests/domain/` with updated imports.

### Phase 2 — Add the remaining domain classes ✅

Implemented in `pinochle/domain/`:
`bid.py`, `hand.py`, `meld.py`, `trick.py`, `scoring.py`, `player.py`, `team.py`, `round.py`, `game.py`.

All tested in `tests/domain/` with plain pytest — no mocking needed.

### Phase 3 — Define the ports ✅

Created `pinochle/ports/` (flat — no `inbound/`/`outbound/` subdirectories).
Contract tests in `tests/ports/` that every adapter must satisfy.

### Phase 4 — Implement outbound adapters ✅

`InMemoryGameState`, `PrintNotification`, `SvgCardImage` — all tested via contract tests
in `tests/adapters/`.

### Phase 5 — Services and strategies ✅

- `GameService` (`pinochle/services/game_service.py`) ✅ — implements `AdminPort` + `PlayerActionPort`; single orchestrator for all game setup and player move use cases.
- `ComputerPlayerStrategy` (`pinochle/strategies/computer_player_strategy.py`) ✅ — stateless rule-based AI helpers; not a port implementation.
- `HttpAdminAdapter` ⬜ — FastAPI routes under `/admin/`.
- `HttpPlayerAdapter` ⬜ — FastAPI routes under `/player/`.

### Phase 6 — Application bootstrap ✅

`pinochle/app.py` — `create_default_app()` wires all implemented components:

```python
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.adapters.print_notification import PrintNotification
from pinochle.adapters.svg_card_image import SvgCardImage
from pinochle.strategies.computer_player_strategy import ComputerPlayerStrategy
from pinochle.services.game_service import GameService

game_state = InMemoryGameState()
notifier = PrintNotification()
card_images = SvgCardImage()
service = GameService(game_state, notifier)
computer = ComputerPlayerStrategy()
```

---

## Key Rules

1. **Domain imports nothing outside of itself.** `pinochle/domain/` may only import from the Python standard library and other modules within `pinochle/domain/`.
2. **Ports import only domain types.** ABCs in `pinochle/ports/` may reference domain dataclasses and enums, but never adapters or frameworks.
3. **Adapters import ports and domain, never each other.** An HTTP adapter must not reference the WebSocket adapter.
4. **Tests for domain logic need no mocking.** If a domain test requires a mock, the logic has leaked out of the domain and should be moved back.

---

## Dependency Direction Summary

```
adapters  →  ports  →  domain
services  →  ports  →  domain
strategies           →  domain
```

All arrows point inward. The domain is unaware of adapters, ports, services, or strategies. Services depend on ports (injected) and the domain. Strategies depend only on domain types. Adapters implement ports and may depend on the domain.
