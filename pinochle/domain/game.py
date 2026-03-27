# pinochle.domain.game
from dataclasses import dataclass
from enum import Enum, auto

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit
from pinochle.domain.player import Player, Position
from pinochle.domain.team import Team
from pinochle.domain.round import Round
from pinochle.domain.scoring import WINNING_SCORE, resolve_round, score_tricks
from pinochle.domain.meld import total_meld


# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------

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
    amount: int | None


@dataclass
class TrumpNamed:
    game_id: str
    suit: Suit


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
    DealerSelected | CardsDealt | BidPlaced | TrumpNamed
    | TrickCompleted | RoundScored | GameOver
)


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------

class GamePhase(Enum):
    SETUP = auto()
    DEALER_SELECTION = auto()
    IN_ROUND = auto()
    FINISHED = auto()


_NS = "NS"
_EW = "EW"


class Game:
    """Aggregate root for a Pinochle game.

    Responsibilities:
    - Hold team and player registrations.
    - Track cumulative scores.
    - Sequence rounds until a team reaches WINNING_SCORE.
    - Emit GameEvents for the NotificationPort to relay to players.
    """

    def __init__(self, game_id: str):
        self.id = game_id
        self.phase = GamePhase.SETUP
        self._teams: dict[str, Team] = {}
        self._players: dict[str, Player] = {}
        self._player_order: list[str] = []  # seat order N, E, S, W
        self._dealer_id: str | None = None
        self._current_round: Round | None = None
        self._events: list[GameEvent] = []

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def add_team(self, team: Team) -> None:
        if self.phase != GamePhase.SETUP:
            raise ValueError("Can only add teams during setup.")
        self._teams[team.id] = team

    def add_player(self, player: Player) -> None:
        if self.phase != GamePhase.SETUP:
            raise ValueError("Can only add players during setup.")
        self._players[player.id] = player
        # Maintain seat order by Position value
        self._player_order = sorted(
            self._players.keys(),
            key=lambda pid: self._players[pid].position.value,
        )

    def start_dealer_selection(self) -> None:
        if len(self._players) != 4:
            raise ValueError("Need exactly four players.")
        if len(self._teams) != 2:
            raise ValueError("Need exactly two teams.")
        self.phase = GamePhase.DEALER_SELECTION

    # ------------------------------------------------------------------
    # Dealer selection
    # ------------------------------------------------------------------

    def set_dealer(self, dealer_id: str) -> None:
        if self.phase != GamePhase.DEALER_SELECTION:
            raise ValueError("Not in dealer-selection phase.")
        if dealer_id not in self._players:
            raise ValueError(f"Unknown player: {dealer_id}")
        self._dealer_id = dealer_id
        self._emit(DealerSelected(game_id=self.id, dealer_player_id=dealer_id))
        self._start_round()

    # ------------------------------------------------------------------
    # Round lifecycle — thin delegation to Round
    # ------------------------------------------------------------------

    def _start_round(self) -> None:
        self._current_round = Round(
            dealer_id=self._dealer_id,
            player_order=self._player_order,
        )
        self.phase = GamePhase.IN_ROUND

    def deal(self) -> None:
        self._current_round.deal()
        for pid in self._player_order:
            self._emit(CardsDealt(
                game_id=self.id,
                player_id=pid,
                cards=list(self._current_round.hand(pid)),
            ))

    def place_bid(self, player_id: str, amount: int | None) -> None:
        self._current_round.place_bid(player_id, amount)
        self._emit(BidPlaced(game_id=self.id, player_id=player_id, amount=amount))

    def name_trump(self, player_id: str, suit: Suit) -> None:
        self._current_round.name_trump(player_id, suit)
        self._emit(TrumpNamed(game_id=self.id, suit=suit))

    def pass_cards(self, player_id: str, cards: list[Card]) -> None:
        self._current_round.pass_cards(player_id, cards)

    def advance_to_playing(self) -> None:
        self._current_round.advance_to_playing()

    def play_card(self, player_id: str, card: Card) -> None:
        winner_id = self._current_round.play_card(player_id, card)
        if winner_id is not None:
            last_trick = self._current_round.tricks[-1]
            self._emit(TrickCompleted(
                game_id=self.id,
                winner_player_id=winner_id,
                cards_played=last_trick.cards,
            ))
            if self._current_round.phase.name == "SCORING":
                self._score_round()

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _player_team_map(self) -> dict[str, str]:
        return {pid: p.team_id for pid, p in self._players.items()}

    def _score_round(self) -> None:
        r = self._current_round
        player_team = self._player_team_map()
        tricks = r.tricks
        last_winner = tricks[-1].winner()

        trick_scores = score_tricks(tricks, last_winner, player_team)
        meld_scores = {
            team_id: total_meld(list(r.hand(pid)), r.trump)
            for pid, p in self._players.items()
            for team_id in [p.team_id]
        }
        # Consolidate meld per team (two players per team)
        consolidated_meld: dict[str, int] = {}
        for pid, p in self._players.items():
            consolidated_meld[p.team_id] = consolidated_meld.get(p.team_id, 0) + total_meld(
                list(r.hand(pid)), r.trump
            )

        net = resolve_round(trick_scores, consolidated_meld, r.bid_winner, r.contract)
        for team_id, points in net.items():
            self._teams[team_id].add_score(points)

        ns_score = self._teams.get(_NS, Team(_NS, "N/S")).cumulative_score
        ew_score = self._teams.get(_EW, Team(_EW, "E/W")).cumulative_score
        self._emit(RoundScored(game_id=self.id, ns_score=ns_score, ew_score=ew_score))

        winner = self._check_winner()
        if winner:
            self.phase = GamePhase.FINISHED
            self._emit(GameOver(game_id=self.id, winning_team_id=winner))
        else:
            self._advance_dealer()
            self._start_round()

    def _check_winner(self) -> str | None:
        over = [t for t in self._teams.values() if t.cumulative_score >= WINNING_SCORE]
        if not over:
            return None
        # If both teams qualify, bid winner wins
        if len(over) > 1:
            return self._current_round.bid_winner and self._players[self._current_round.bid_winner].team_id
        return over[0].id

    def _advance_dealer(self) -> None:
        idx = self._player_order.index(self._dealer_id)
        self._dealer_id = self._player_order[(idx + 1) % 4]

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def _emit(self, event: GameEvent) -> None:
        self._events.append(event)

    def pop_events(self) -> list[GameEvent]:
        """Drain and return all pending events."""
        events = list(self._events)
        self._events.clear()
        return events

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def teams(self) -> dict[str, Team]:
        return dict(self._teams)

    @property
    def players(self) -> dict[str, Player]:
        return dict(self._players)

    @property
    def current_round(self) -> Round | None:
        return self._current_round
