from __future__ import annotations

# pinochle.domain.game
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit
from pinochle.domain.player import Player
from pinochle.domain.team import Team

if TYPE_CHECKING:
    from pinochle.services.round import Round


# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------

@dataclass
class DealerSelected:
    """Emitted when dealer selection is resolved and a dealer has been chosen.

    Attributes:
        game_id: The game in which dealer selection occurred.
        dealer_player_id: The player who will deal the first round.
    """

    game_id: str
    dealer_player_id: str


@dataclass
class CardsDealt:
    """Emitted once per player after a round's cards have been dealt.

    One event is published per player so that each recipient receives only
    their own private hand.

    Attributes:
        game_id: The game in which the deal occurred.
        player_id: The player to whom this hand belongs.
        cards: The 12 cards dealt to the player.
    """

    game_id: str
    player_id: str
    cards: list[Card]


@dataclass
class BidPlaced:
    """Emitted after each bid or pass during the bidding phase.

    Attributes:
        game_id: The game in which the bid occurred.
        player_id: The player who bid or passed.
        amount: The bid value, or ``None`` if the player passed.
    """

    game_id: str
    player_id: str
    amount: int | None


@dataclass
class TrumpNamed:
    """Emitted when the bid winner declares the trump suit for the round.

    Attributes:
        game_id: The game in which trump was declared.
        suit: The suit designated as trump for this round.
    """

    game_id: str
    suit: Suit


@dataclass
class TrickCompleted:
    """Emitted after all four players have played a card into the current trick.

    Attributes:
        game_id: The game in which the trick was completed.
        winner_player_id: The player who won the trick and will lead the next.
        cards_played: The four cards played, in the order they were played.
    """

    game_id: str
    winner_player_id: str
    cards_played: list[Card]


@dataclass
class RoundScored:
    """Emitted after a round's trick and meld points have been tallied and applied.

    Attributes:
        game_id: The game in which scoring occurred.
        ns_score: The North/South team's updated cumulative score.
        ew_score: The East/West team's updated cumulative score.
    """

    game_id: str
    ns_score: int
    ew_score: int


@dataclass
class GameOver:
    """Emitted when a team's cumulative score reaches or exceeds the winning threshold.

    Attributes:
        game_id: The game that has ended.
        winning_team_id: The id of the team that won the game.
    """

    game_id: str
    winning_team_id: str


GameEvent = (
    DealerSelected | CardsDealt | BidPlaced | TrumpNamed
    | TrickCompleted | RoundScored | GameOver
)


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------

class GamePhase(Enum):
    """High-level lifecycle states for a persisted ``Game`` aggregate.

    States advance strictly in order:
    ``SETUP`` → ``DEALER_SELECTION`` → ``IN_ROUND`` (repeating) → ``FINISHED``.

    - ``SETUP``: Teams and players are being registered; no play yet.
    - ``DEALER_SELECTION``: All players draw cards to determine the first dealer.
    - ``IN_ROUND``: A ``Round`` is in progress.
    - ``FINISHED``: A team has reached the winning score; no further play.
    """

    SETUP = auto()
    DEALER_SELECTION = auto()
    IN_ROUND = auto()
    FINISHED = auto()


class Game:
    """Aggregate root for persisted game state.

    The `Game` entity stores long-lived state and emits domain events.
    Round/game orchestration lives in the service layer.
    """

    def __init__(self, game_id: str):
        """Create a new game aggregate in the setup phase."""
        self.id = game_id
        self.phase = GamePhase.SETUP
        self._teams: dict[str, Team] = {}
        self._players: dict[str, Player] = {}
        self._player_order: list[str] = []
        self._dealer_id: str | None = None
        self._current_round: Round | None = None
        self._events: list[GameEvent] = []

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def add_team(self, team: Team) -> None:
        """Register a team while the game is still being configured."""
        if self.phase != GamePhase.SETUP:
            raise ValueError("Can only add teams during setup.")
        self._teams[team.id] = team

    def add_player(self, player: Player) -> None:
        """Register a player and refresh the seat-ordered turn list."""
        if self.phase != GamePhase.SETUP:
            raise ValueError("Can only add players during setup.")
        self._players[player.id] = player
        self._player_order = sorted(
            self._players.keys(),
            key=lambda pid: self._players[pid].position.value,
        )

    def start_dealer_selection(self) -> None:
        """Validate setup completeness and move into dealer selection."""
        if len(self._players) != 4:
            raise ValueError("Need exactly four players.")
        if len(self._teams) != 2:
            raise ValueError("Need exactly two teams.")
        self.phase = GamePhase.DEALER_SELECTION

    # ------------------------------------------------------------------
    # State transitions coordinated by services
    # ------------------------------------------------------------------

    def set_dealer(self, dealer_id: str) -> None:
        """Record the player who will deal the next round."""
        if self.phase != GamePhase.DEALER_SELECTION:
            raise ValueError("Not in dealer-selection phase.")
        if dealer_id not in self._players:
            raise ValueError(f"Unknown player: {dealer_id}")
        self._dealer_id = dealer_id

    def begin_round(self, round_state: "Round") -> None:
        """Attach the active round state and enter round play."""
        self._current_round = round_state
        self.phase = GamePhase.IN_ROUND

    def add_score(self, team_id: str, points: int) -> None:
        """Apply points to a team's cumulative total."""
        self._teams[team_id].add_score(points)

    def next_dealer(self) -> str:
        """Return the next dealer in clockwise player order."""
        idx = self._player_order.index(self._dealer_id)
        return self._player_order[(idx + 1) % 4]

    def set_finished(self) -> None:
        """Mark the game as finished."""
        self.phase = GamePhase.FINISHED

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def emit(self, event: GameEvent) -> None:
        """Append a domain event to the pending event queue."""
        self._events.append(event)

    def pop_events(self) -> list[GameEvent]:
        """Return and clear all pending domain events."""
        events = list(self._events)
        self._events.clear()
        return events

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def teams(self) -> dict[str, Team]:
        """Return a shallow copy of the registered teams by id."""
        return dict(self._teams)

    @property
    def players(self) -> dict[str, Player]:
        """Return a shallow copy of the registered players by id."""
        return dict(self._players)

    @property
    def player_order(self) -> list[str]:
        """Return player ids in table order."""
        return list(self._player_order)

    @property
    def dealer_id(self) -> str | None:
        """Return the current dealer, if one has been selected."""
        return self._dealer_id

    @property
    def current_round(self) -> "Round" | None:
        """Return the current round state, if the game is in a round."""
        return self._current_round

    def team_id_for_player(self, player_id: str) -> str:
        """Return the team id associated with ``player_id``."""
        return self._players[player_id].team_id
