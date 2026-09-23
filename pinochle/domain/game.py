from __future__ import annotations

# pinochle.domain.game
from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import TYPE_CHECKING

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit
from pinochle.domain.errors import IllegalActionError, SetupError, WrongPhaseError
from pinochle.domain.hold import Hold, HoldReason
from pinochle.domain.meld import MeldUnit
from pinochle.domain.player import Player, PlayerType
from pinochle.domain.team import Team
from pinochle.domain.team_round_score import TeamRoundScore
from pinochle.domain.trick import TrickPlay

if TYPE_CHECKING:
    from pinochle.services.round import Round


# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------

@dataclass
class GameConfigured:
    """Emitted when setup closes and the table is fixed for the whole game.

    Carries everything a client needs to draw the table before a single card
    exists: who is sitting where, under what name, whether each seat is human
    or computer, and what the partnerships are called.  Seats never change
    afterwards (FR-2a), so this event is published once.

    Attributes:
        game_id: The game being configured.
        players: All four players, in clockwise seat order from North.
        teams: The two partnerships, whose ids are fixed by the seating.
        winning_score: The cumulative score that ends the game (FR-67).
    """

    game_id: str
    players: list[Player]
    teams: list[Team]
    winning_score: int


@dataclass
class DealerSelectionStarted:
    """Emitted when a face-down spread is laid out for the dealer draw.

    Published once when the game starts, and again after every tie, because a
    tie replaces the spread wholesale rather than re-drawing within it (FR-14).

    Attributes:
        game_id: The game in which the spread was laid out.
        spread_size: How many addressable positions the spread offers (FR-11a).
    """

    game_id: str
    spread_size: int


@dataclass
class DrawMade:
    """Emitted when one player turns a card in the dealer-selection spread.

    Public, because FR-15 requires each drawn card be revealed to everyone —
    the drawing player learns it by the same route as the three watching.

    Attributes:
        game_id: The game in which the draw was made.
        player_id: The player who drew.
        position: The spread position taken, which no one else may now take.
        card: The card lying at that position.
    """

    game_id: str
    player_id: str
    position: int
    card: Card


@dataclass
class DrawTied:
    """Emitted when two or more players draw the highest rank.

    The whole selection is repeated with a fresh spread and all four players
    drawing again (FR-14), so this event is always followed by another
    ``DealerSelectionStarted``.

    Attributes:
        game_id: The game in which the draw was tied.
        cards: The card each player drew in the round being discarded.
    """

    game_id: str
    cards: dict[str, Card]


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
class RoundStarted:
    """Emitted when a fresh round has been dealt and bidding is about to open.

    Precedes the per-player ``CardsDealt`` events, so a client can reset the
    table before the new hand arrives.

    Attributes:
        game_id: The game in which the round began.
        round_number: The round's ordinal, counting from one.
        dealer_player_id: Who dealt it.
    """

    game_id: str
    round_number: int
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
        current_high: The high bid standing after this action.
    """

    game_id: str
    player_id: str
    amount: int | None
    current_high: int


@dataclass
class ContractOffered:
    """Emitted when a lone bidder is offered the chance to decline (FR-32).

    Public, so that the other three players know why the auction has paused
    rather than moving on to trump.

    Attributes:
        game_id: The game in which the contract was offered.
        player_id: The lone bidder holding the decision.
        amount: The bid they would be held to.
    """

    game_id: str
    player_id: str
    amount: int


@dataclass
class RoundAbandoned:
    """Emitted when a round ends before any card is played.

    Happens when all four players pass, or when a lone bidder declines the
    contract they were left holding.  No score changes; the deal moves on.

    Attributes:
        game_id: The game in which the round was abandoned.
        declined_by: The lone bidder who declined, or ``None`` if nobody bid.
    """

    game_id: str
    declined_by: str | None


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
class CardsPassed:
    """Emitted when one player hands four cards to their partner.

    Visible only to the two players on the auction-winning team; the opposing
    team must not learn which cards were exchanged.

    Attributes:
        game_id: The game in which the pass occurred.
        from_player_id: The player giving the cards.
        to_player_id: The partner receiving them.
        cards: The four cards passed.
    """

    game_id: str
    from_player_id: str
    to_player_id: str
    cards: list[Card]


@dataclass
class MeldExposed:
    """Emitted once per player when meld is laid on the table after the pass.

    Meld is public: every player sees every other player's combinations, so
    this event is broadcast.  It carries the points recorded for scoring, which
    are fixed at this moment and not recomputed once trick play empties the
    hands.

    Attributes:
        game_id: The game in which meld was exposed.
        player_id: The player whose meld this is.
        cards: The physical cards laid face-up for these combinations.
        units: The combinations detected in the player's hand.
        total: The points those combinations are worth.
    """

    game_id: str
    player_id: str
    cards: list[Card]
    units: list[MeldUnit]
    total: int


@dataclass
class PlayBegun:
    """Emitted when the auction winner ends the meld display and leads off.

    The MELDING phase is untimed and only the auction winner may end it
    (FR-50a), so this event is what clears the exposed meld from every client
    at the same moment.

    Attributes:
        game_id: The game in which play began.
        leader_player_id: The auction winner, who leads the first trick.
    """

    game_id: str
    leader_player_id: str


@dataclass
class ContractTossedIn:
    """Emitted when the auction winner concedes rather than play the contract.

    Attributes:
        game_id: The game in which the contract was given up.
        player_id: The auction winner who tossed it in.
    """

    game_id: str
    player_id: str


@dataclass
class SeatReplaced:
    """Emitted when a computer takes over a seat whose player has gone (RT-12a).

    A seat is replaced, never re-created: the id, the position and the
    partnership all stay as they were, so the round in progress — the hand
    dealt to that seat, its bids, its meld — carries on belonging to it.  What
    changes is who decides its moves, which is exactly what ``type`` says.

    The name stays too.  It is the name the other three players have been
    calling that seat all evening, and a computer taking the cards over does
    not make them stop; clients mark the seat as computer-played from
    ``type``, which is the same mark an all-computer table already carries
    (UI-3).

    Attributes:
        game_id: The game whose table has changed.
        player_id: The seat now played by the computer.
        name: The seat's display name, unchanged by the replacement.
        type: Who plays the seat now — always ``computer``.
    """

    game_id: str
    player_id: str
    name: str
    type: PlayerType


@dataclass
class SeatThinking:
    """Emitted when a computer seat's move delay begins (FR-75c, RT-7).

    Opens a timed pause that the matching action event closes, so that clients
    can show the seat as thinking without running a clock of their own (RT-10).
    Published by the computer driver rather than by the round, since the delay
    is an application concern and not a rule of the game.

    Attributes:
        game_id: The game in which the seat is thinking.
        player_id: The computer seat on the clock.
    """

    game_id: str
    player_id: str


@dataclass
class CardPlayed:
    """Emitted as each card is played, before the trick is complete.

    FR-57 requires a played card become visible to all four players as soon as
    it is played, so this is published on every play rather than only when the
    fourth card falls.

    Attributes:
        game_id: The game in which the card was played.
        player_id: The player who played it.
        card: The card played.
    """

    game_id: str
    player_id: str
    card: Card


@dataclass
class TrickCompleted:
    """Emitted after all four players have played a card into the current trick.

    Attributes:
        game_id: The game in which the trick was completed.
        winner_player_id: The player who won the trick and will lead the next.
        plays: The four (player_id, card) pairs, in the order they were played.
    """

    game_id: str
    winner_player_id: str
    plays: list[TrickPlay]


@dataclass
class TrickCleared:
    """Emitted when a completed trick is swept from the table to its winner.

    Closes the trick-clear pause that ``TrickCompleted`` opened (UI-15).  The
    pause is counted by the server, so this event — not a clock in the client —
    is what returns the table to play (RT-8, RT-10).

    Attributes:
        game_id: The game in which the trick was cleared.
        winner_player_id: The player who collected the four cards.
        next_leader_player_id: Who leads the next trick, which is always the
            winner (FR-56), or ``None`` when that was the twelfth trick and the
            round is over.
    """

    game_id: str
    winner_player_id: str
    next_leader_player_id: str | None


@dataclass
class RoundScored:
    """Emitted after a round's trick and meld points have been tallied and applied.

    Carries the full breakdown FR-66 requires be displayed: for each team its
    meld, captured card points, last-trick bonus, round total, and new
    cumulative score, together with whether the auction-winning team made the
    contract or went set.

    Attributes:
        game_id: The game in which scoring occurred.
        round_number: The round that was scored.
        bid_team_id: The team that won the auction.
        bid_winner_player_id: The player who won it.
        contract: The amount that team had to meet.
        made_contract: Whether they met it.  ``False`` for a tossed-in round,
            in which the contract was never played for.
        tossed_in: Whether the auction winner conceded rather than play (FR-50b).
        teams: One line of arithmetic per team.
    """

    game_id: str
    round_number: int
    bid_team_id: str
    bid_winner_player_id: str
    contract: int
    made_contract: bool
    tossed_in: bool
    teams: list[TeamRoundScore]


@dataclass
class TurnPrompt:
    """Emitted to the acting seat whenever the current player changes.

    Regenerated, not resumed, at each change: the client is *told* what is
    legal rather than deriving it (ARC-2, UI-9), so this carries the
    phase-specific options from design.md §6.5's tagged union — the minimum
    bid while bidding, the legal cards while playing, and so on.  Addressed
    to one seat, so it is never broadcast.

    Attributes:
        game_id: The game the prompt belongs to.
        player_id: The seat being prompted.
        phase: The round phase the options belong to.
        options: The phase-specific fields, e.g. ``{"minimum_bid": 260,
            "may_pass": True}`` while bidding, or ``{"legal_plays": [...]}``
            while playing.
    """

    game_id: str
    player_id: str
    phase: str
    options: dict


@dataclass
class GameOver:
    """Emitted when a team's cumulative score reaches or exceeds the winning threshold.

    Attributes:
        game_id: The game that has ended.
        winning_team_id: The id of the team that won the game.
        ns_score: The North/South team's final cumulative score.
        ew_score: The East/West team's final cumulative score.
    """

    game_id: str
    winning_team_id: str
    ns_score: int
    ew_score: int


@dataclass
class HoldBegun:
    """Emitted when the game stops on a hold (RT-13).

    RT-10 wants a pause delimited by events rather than inferred from a
    clock, and this is the opening one.  The hold is also on the turn header
    of every frame, which is what a client reconnecting into the middle of a
    pause reads (RT-5a); this event is what tells a client already watching
    that the pause has begun.

    Attributes:
        game_id: The game that has stopped.
        hold_id: Identifies this hold, and is what a release must name.
        reason: What the table is being held for, which the client turns into
            words of its own (UI-19).
        seconds: The interval, for a hold the server ends by the clock;
            ``None`` for one awaiting a player.
        ackable: Whether any seat may release it (RT-13).
    """

    game_id: str
    hold_id: int
    reason: HoldReason
    seconds: float | None
    ackable: bool


@dataclass
class HoldEnded:
    """Emitted when a hold is released, by the clock or by a player (RT-13).

    The closing half of RT-10's delimiting pair.  Emitted once, by whichever
    of the two ended the hold: a release naming a hold that has already ended
    changes nothing and emits nothing, so two players clicking at the same
    moment produce one of these and not two.

    Attributes:
        game_id: The game that is moving again.
        hold_id: The hold that ended.
        reason: What it had been held for.
    """

    game_id: str
    hold_id: int
    reason: HoldReason


GameEvent = (
    GameConfigured | DealerSelectionStarted | DrawMade | DrawTied
    | DealerSelected | RoundStarted | CardsDealt | BidPlaced | ContractOffered
    | RoundAbandoned | TrumpNamed | CardsPassed | MeldExposed | PlayBegun
    | ContractTossedIn | SeatReplaced | SeatThinking | CardPlayed | TrickCompleted
    | TrickCleared | TurnPrompt | RoundScored | GameOver
    | HoldBegun | HoldEnded
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
        self._round_number = 0
        self._current_round: Round | None = None
        self._hold: Hold | None = None
        self._next_hold_id = 0
        self._events: list[GameEvent] = []

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def add_team(self, team: Team) -> None:
        """Register a team while the game is still being configured."""
        if self.phase != GamePhase.SETUP:
            raise WrongPhaseError("Can only add teams during setup.")
        self._teams[team.id] = team

    def add_player(self, player: Player) -> None:
        """Register a player and refresh the seat-ordered turn list."""
        if self.phase != GamePhase.SETUP:
            raise WrongPhaseError("Can only add players during setup.")
        self._players[player.id] = player
        self._player_order = sorted(
            self._players.keys(),
            key=lambda pid: self._players[pid].position.value,
        )

    def start_dealer_selection(self) -> None:
        """Validate setup completeness and move into dealer selection."""
        if len(self._players) != 4:
            raise SetupError("Need exactly four players.")
        if len(self._teams) != 2:
            raise SetupError("Need exactly two teams.")
        self.phase = GamePhase.DEALER_SELECTION

    # ------------------------------------------------------------------
    # State transitions coordinated by services
    # ------------------------------------------------------------------

    def set_dealer(self, dealer_id: str) -> None:
        """Record the player who will deal the next round."""
        if self.phase != GamePhase.DEALER_SELECTION:
            raise WrongPhaseError("Not in dealer-selection phase.")
        if dealer_id not in self._players:
            raise IllegalActionError(f"Unknown player: {dealer_id}")
        self._dealer_id = dealer_id

    def begin_round(self, round_state: "Round") -> None:
        """Attach the active round state, count the round, and enter round play."""
        self._current_round = round_state
        self._round_number += 1
        self.phase = GamePhase.IN_ROUND

    def add_score(self, team_id: str, points: int) -> None:
        """Apply points to a team's cumulative total."""
        self._teams[team_id].add_score(points)

    def next_dealer(self) -> str:
        """Return the next dealer in clockwise player order."""
        idx = self._player_order.index(self._dealer_id)
        return self._player_order[(idx + 1) % 4]

    def rotate_dealer(self) -> None:
        """Pass the deal one seat clockwise between rounds.

        Distinct from ``set_dealer``, which belongs to the once-per-game
        dealer-selection draw; rotation happens in every later round and must
        not pretend the game has re-entered that phase.
        """
        self._dealer_id = self.next_dealer()

    def seat_computer(self, player_id: str) -> Player:
        """Hand a seat to the computer, and announce that it has changed (RT-12a).

        The seat itself is untouched: same id, same position, same
        partnership, same cards.  Only who decides its moves changes, which
        is what lets a round carry on from where the departed player left it
        rather than being dealt again.

        Refused once the game is over, because there is nothing left for the
        computer to play; refused for a seat already played by the computer,
        because that is an administrator acting on a stale console and the
        honest answer is that the seat they meant is not the one they are
        looking at.
        """
        if self.phase == GamePhase.FINISHED:
            raise WrongPhaseError("The game is over; there is nothing left to play.")
        player = self._players.get(player_id)
        if player is None:
            raise IllegalActionError(f"Unknown player: {player_id}")
        if player.type == PlayerType.COMPUTER:
            raise IllegalActionError(
                f"{player.position.name} is already played by the computer.")

        seated = replace(player, type=PlayerType.COMPUTER)
        self._players[player_id] = seated
        self.emit(SeatReplaced(
            game_id=self.id,
            player_id=seated.id,
            name=seated.name,
            type=seated.type,
        ))
        return seated

    def set_finished(self) -> None:
        """Mark the game as finished."""
        self.phase = GamePhase.FINISHED

    # ------------------------------------------------------------------
    # Holds
    # ------------------------------------------------------------------

    def begin_hold(
        self,
        reason: HoldReason,
        *,
        seconds: float | None = None,
        ackable: bool = False,
    ) -> Hold:
        """Stop the game on a hold, and announce that it has stopped (RT-13).

        Ids count up per game and are never reused, which is what lets a
        release name the hold it means rather than merely asserting that
        *some* hold should end.  Without that, a click that arrived a moment
        late would release the hold after the one it was aimed at.
        """
        self._next_hold_id += 1
        hold = Hold(
            id=self._next_hold_id, reason=reason, seconds=seconds, ackable=ackable)
        self._hold = hold
        self.emit(HoldBegun(
            game_id=self.id,
            hold_id=hold.id,
            reason=hold.reason,
            seconds=hold.seconds,
            ackable=hold.ackable,
        ))
        return hold

    def end_hold(self, hold_id: int) -> Hold | None:
        """Release the hold ``hold_id`` names, or return ``None`` if it has gone.

        Idempotent by RT-13: naming a hold that has already ended — because
        another seat released it first, or because the same seat clicked
        twice — is a no-op rather than an error, and emits nothing.  The
        caller distinguishes the two by the return value, not by an
        exception, because only one of them is worth telling a player about
        and it is not this one.
        """
        hold = self._hold
        if hold is None or hold.id != hold_id:
            return None
        self._hold = None
        self.emit(HoldEnded(game_id=self.id, hold_id=hold.id, reason=hold.reason))
        return hold

    @property
    def current_hold(self) -> Hold | None:
        """Return the hold the game is stopped on, if it is stopped."""
        return self._hold

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
    def round_number(self) -> int:
        """Return how many rounds have been dealt, counting from one.

        An abandoned round (FR-31, FR-32) consumes a number like any other:
        it was dealt, bid, and thrown in, and the players saw it happen.
        """
        return self._round_number

    @property
    def current_round(self) -> "Round" | None:
        """Return the current round state, if the game is in a round."""
        return self._current_round

    def team_id_for_player(self, player_id: str) -> str:
        """Return the team id associated with ``player_id``."""
        return self._players[player_id].team_id
