# Hexagonal Architecture Refactor Plan

## Overview

This document describes a plan for refactoring the pinochle project to the **Ports and Adapters** (hexagonal) architecture. The goal is to isolate the pure game domain from delivery mechanisms (HTTP/WebSocket, CLI) and infrastructure (persistence, external services), making it easy to test, swap, and extend each layer independently.

---

## Current State

```
pinochle/
├── cards/          # Domain objects: Rank, Suit, Card (implemented)
├── players/        # Stub (empty)
tests/
├── test_cards.py
├── test_ranks.py
└── test_suit.py
```

The `cards` module is a solid domain foundation. Nothing else is implemented yet. This is an ideal time to establish the hexagonal structure before the remaining domain and infrastructure code is written.

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

## Target Directory Structure

```
pinochle/                          # top-level package
│
├── domain/                        # Pure game logic — no I/O, no frameworks
│   ├── __init__.py
│   ├── cards/
│   │   ├── __init__.py            # re-exports Card, Rank, Suit, Deck
│   │   ├── rank.py                # Rank enum (existing, move here)
│   │   ├── suit.py                # Suit enum (existing, move here)
│   │   ├── card.py                # Card class (existing, move here)
│   │   └── deck.py                # Deck (48-card pinochle deck)
│   ├── game.py                    # Game aggregate root
│   ├── round.py                   # Round state machine
│   ├── team.py                    # Team value object
│   ├── player.py                  # Player entity (position, name, type)
│   ├── hand.py                    # A player's current hand of cards
│   ├── bid.py                     # Bid value object and bidding rules
│   ├── meld.py                    # Meld detection and scoring
│   ├── trick.py                   # Trick-taking logic
│   └── scoring.py                 # Round and game scoring rules
│
├── ports/                         # Interfaces / contracts
│   ├── __init__.py
│   ├── inbound/
│   │   ├── __init__.py
│   │   ├── admin_port.py          # AdminPort ABC — game setup commands
│   │   └── player_action_port.py  # PlayerActionPort ABC — player moves
│   └── outbound/
│       ├── __init__.py
│       ├── game_state_port.py     # GameStatePort ABC — load/save game state
│       ├── notification_port.py   # NotificationPort ABC — push events to players
│       └── card_image_port.py     # CardImagePort ABC — resolve card image assets
│
├── adapters/                      # Concrete implementations of ports
│   ├── __init__.py
│   ├── inbound/
│   │   ├── __init__.py
│   │   ├── http_admin_adapter.py      # FastAPI/Flask routes for admin actions
│   │   ├── http_player_adapter.py     # FastAPI/Flask routes for player actions
│   │   └── computer_player_adapter.py # AI driver implementing PlayerActionPort
│   └── outbound/
│       ├── __init__.py
│       ├── in_memory_game_state.py    # GameStatePort — stores state in a dict
│       ├── websocket_notification.py  # NotificationPort — pushes via WebSocket
│       └── svg_card_image.py          # CardImagePort — serves SVG/PNG from resources/
│
└── cards/
    └── resources/                 # SVG/PNG card images (no change)
        └── svg_playing_cards/
            ├── fronts/
            ├── backs/
            └── other/

tests/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── test_rank.py               # (rename/move existing test_ranks.py)
│   ├── test_suit.py               # (move existing test_suit.py)
│   ├── test_card.py               # (rename/move existing test_cards.py)
│   ├── test_deck.py
│   ├── test_bid.py
│   ├── test_meld.py
│   ├── test_trick.py
│   └── test_scoring.py
├── ports/
│   ├── __init__.py
│   └── (contract tests asserting adapter compliance)
└── adapters/
    ├── __init__.py
    ├── test_in_memory_game_state.py
    ├── test_computer_player.py
    └── test_svg_card_image.py
```

---

## Ports (Interfaces)

### Inbound Ports — what callers ask of the application

#### `AdminPort` (`ports/inbound/admin_port.py`)

```python
from abc import ABC, abstractmethod
from pinochle.domain.player import Player
from pinochle.domain.team import Team

class AdminPort(ABC):
    @abstractmethod
    def create_game(self) -> str:
        """Create a new game and return its ID."""

    @abstractmethod
    def add_player(self, game_id: str, player: Player) -> None:
        """Register a player (human or computer) into the pending game."""

    @abstractmethod
    def assign_teams(self, game_id: str, ns: Team, ew: Team) -> None:
        """Assign the two partnerships."""

    @abstractmethod
    def start_game(self, game_id: str) -> None:
        """Shuffle the deck and begin dealer selection."""
```

#### `PlayerActionPort` (`ports/inbound/player_action_port.py`)

```python
from abc import ABC, abstractmethod
from pinochle.domain.cards import Card, Suit

class PlayerActionPort(ABC):
    @abstractmethod
    def draw_for_deal(self, game_id: str, player_id: str) -> Card:
        """Player draws a card to determine dealer."""

    @abstractmethod
    def place_bid(self, game_id: str, player_id: str, amount: int | None) -> None:
        """Place a bid (None = pass)."""

    @abstractmethod
    def name_trump(self, game_id: str, player_id: str, suit: Suit) -> None:
        """Bid winner names the trump suit."""

    @abstractmethod
    def pass_cards(self, game_id: str, player_id: str, cards: list[Card]) -> None:
        """Pass four cards to partner."""

    @abstractmethod
    def play_card(self, game_id: str, player_id: str, card: Card) -> None:
        """Play a card into the current trick."""
```

### Outbound Ports — what the domain requires from infrastructure

#### `GameStatePort` (`ports/outbound/game_state_port.py`)

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

#### `NotificationPort` (`ports/outbound/notification_port.py`)

```python
from abc import ABC, abstractmethod
from pinochle.domain.game import GameEvent

class NotificationPort(ABC):
    @abstractmethod
    def notify(self, player_id: str, event: GameEvent) -> None:
        """Push a game event to a specific player."""

    @abstractmethod
    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Push an event to all players in the game."""
```

#### `CardImagePort` (`ports/outbound/card_image_port.py`)

```python
from abc import ABC, abstractmethod
from pinochle.domain.cards import Card

class CardImagePort(ABC):
    @abstractmethod
    def get_image_path(self, card: Card, format: str = "svg") -> str:
        """Return a URL path or filesystem path for the card face image."""

    @abstractmethod
    def get_back_path(self, format: str = "svg") -> str:
        """Return a path for the card back image."""
```

---

## Adapters (Concrete Implementations)

### Inbound Adapters

| Adapter | Port implemented | Technology |
|---|---|---|
| `HttpAdminAdapter` | `AdminPort` | FastAPI routes under `/admin/` |
| `HttpPlayerAdapter` | `PlayerActionPort` | FastAPI routes under `/player/` |
| `ComputerPlayerAdapter` | `PlayerActionPort` | Rule-based or minimax AI, no HTTP |

The computer player adapter is called directly by the game engine (not over the network), which is the key advantage of the port abstraction — human and computer players are interchangeable behind the same interface.

### Outbound Adapters

| Adapter | Port implemented | Notes |
|---|---|---|
| `InMemoryGameState` | `GameStatePort` | Dict-backed; sufficient for single-process dev/test |
| `WebSocketNotification` | `NotificationPort` | Pushes JSON events over WebSocket connections |
| `SvgCardImage` | `CardImagePort` | Resolves paths into `cards/resources/svg_playing_cards/` |

---

## Domain Events

The `Game` aggregate root emits events that the `NotificationPort` broadcasts to players. Defining events as plain dataclasses in the domain keeps them framework-free.

```python
# domain/game.py (partial)
from dataclasses import dataclass
from pinochle.domain.cards import Card

@dataclass
class DealerSelected:
    game_id: str
    dealer_player_id: str

@dataclass
class CardsDealt:
    game_id: str
    player_id: str
    cards: list[Card]

@dataclass
class BidPlaced:
    game_id: str
    player_id: str
    amount: int | None   # None = pass

@dataclass
class TrumpNamed:
    game_id: str
    suit: str

@dataclass
class TrickCompleted:
    game_id: str
    winner_player_id: str
    cards_played: list[Card]

@dataclass
class RoundScored:
    game_id: str
    ns_score: int
    ew_score: int

@dataclass
class GameOver:
    game_id: str
    winning_team_id: str

GameEvent = (
    DealerSelected | CardsDealt | BidPlaced | TrumpNamed |
    TrickCompleted | RoundScored | GameOver
)
```

---

## Migration Steps

### Phase 1 — Restructure the cards module (no logic changes)

1. Create `pinochle/domain/` and `pinochle/domain/cards/`.
2. Move `rank.py`, `suit.py`, `card.py` into `pinochle/domain/cards/`.
3. Remove the `IS_WINDOWS()` helper from `cards/__init__.py`; move it to `domain/cards/suit.py` as a module-private function.
4. Update `suit.py` to import from `pinochle.domain.cards` instead of the old `cards` package.
5. Move test files into `tests/domain/` and update imports.
6. Verify all existing tests still pass.

### Phase 2 — Add the remaining domain classes

Implement the following in `pinochle/domain/`, with no imports from `ports/` or `adapters/`:

- `deck.py` — `Deck`: shuffle, deal N cards, 48-card Pinochle composition (two copies of 9–A per suit).
- `hand.py` — `Hand`: a player's current cards; methods for legal plays, meld detection input.
- `bid.py` — `Bid` value object; `BiddingRound` with pass/bid validation (multiples of 10, minimum 250).
- `meld.py` — `detect_meld(hand, trump)` returning a list of `MeldUnit` with name and point value.
- `trick.py` — `Trick`: tracks four cards played, determines winner given trump suit.
- `scoring.py` — `score_tricks(tricks)` and `score_round(...)` following the point table in `design.md`.
- `player.py` — `Player` dataclass (id, name, type, position, team_id).
- `team.py` — `Team` dataclass (id, name, cumulative_score).
- `round.py` — `Round` state machine: DEALING → BIDDING → TRUMP → PASSING → MELDING → PLAYING → SCORING.
- `game.py` — `Game` aggregate: holds teams, current round, cumulative scores; emits `GameEvent`s.

Write unit tests for each module in `tests/domain/` as you go. Because the domain has no I/O, every test is a plain pytest function with no mocking required.

### Phase 3 — Define the ports

1. Create `pinochle/ports/inbound/` and `pinochle/ports/outbound/`.
2. Implement the ABCs described in the **Ports** section above.
3. Write *contract tests* in `tests/ports/` that any adapter must satisfy — a parametrized test fixture that receives a concrete adapter and asserts the required behavior.

### Phase 4 — Implement outbound adapters

1. `InMemoryGameState` — implement and test first; this unlocks integration testing of the full game flow without a database.
2. `SvgCardImage` — thin wrapper around the existing `resources/` directory; resolve `card.rank.rank_name` and `card.suit.character` to a filename.
3. `WebSocketNotification` — defer until the web framework is chosen; start with a `PrintNotification` adapter that logs events to stdout for development.

### Phase 5 — Implement inbound adapters

1. `ComputerPlayerAdapter` — implement a simple rule-based AI first (play highest legal card). Wire it into integration tests to exercise the full game loop without a web server.
2. `HttpAdminAdapter` and `HttpPlayerAdapter` — add FastAPI (recommended for async WebSocket support) or Flask routes that delegate to the domain use-case functions. No game logic in the adapters.

### Phase 6 — Application bootstrap

Create `pinochle/app.py` (or an entry-point script) that wires the ports and adapters together:

```python
from pinochle.adapters.outbound.in_memory_game_state import InMemoryGameState
from pinochle.adapters.outbound.websocket_notification import WebSocketNotification
from pinochle.adapters.outbound.svg_card_image import SvgCardImage
from pinochle.adapters.inbound.http_admin_adapter import HttpAdminAdapter
from pinochle.adapters.inbound.http_player_adapter import HttpPlayerAdapter

game_state = InMemoryGameState()
notifier = WebSocketNotification()
card_images = SvgCardImage()

admin_handler = HttpAdminAdapter(game_state, notifier)
player_handler = HttpPlayerAdapter(game_state, notifier)
```

The domain never sees these wiring details — only the port interfaces.

---

## Key Rules

1. **Domain imports nothing outside of itself.** `pinochle/domain/` may only import from the Python standard library and other modules within `pinochle/domain/`.
2. **Ports import only domain types.** ABCs in `pinochle/ports/` may reference domain dataclasses and enums, but never adapters or frameworks.
3. **Adapters import ports and domain, never each other.** An HTTP adapter must not reference the WebSocket adapter.
4. **Tests for domain logic need no mocking.** If a domain test requires a mock, the logic has leaked out of the domain and should be moved back.
5. **The `IS_WINDOWS()` platform check belongs in the domain** (it changes how a Suit renders), but should be a private function, not exported as part of the public API.

---

## Dependency Direction Summary

```
adapters  →  ports  →  domain
```

All arrows point inward. The domain is unaware of adapters or ports. Ports are unaware of adapters.
