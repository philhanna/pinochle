# pinochle.services.game_service
import uuid
from dataclasses import dataclass, field

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.deck import Deck
from pinochle.domain.cards.suit import Suit
from pinochle.domain.game import (
    BidPlaced,
    CardsDealt,
    CardsPassed,
    DealerSelected,
    Game,
    GameEvent,
    GamePhase,
    GameOver,
    MeldExposed,
    RoundScored,
    TrickCompleted,
    TrumpNamed,
)
from pinochle.domain.player import Player
from pinochle.domain.scoring import WINNING_SCORE, resolve_round, score_tricks
from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID, Team
from pinochle.ports.admin_port import AdminPort
from pinochle.ports.game_state_port import GameStatePort
from pinochle.ports.notification_port import NotificationPort
from pinochle.ports.player_action_port import PlayerActionPort
from pinochle.ports.scheduler_port import SchedulerPort
from pinochle.services.round import Round, RoundPhase

# How long the exposed meld stays on the table before trick play begins.
MELD_DISPLAY_SECONDS = 8.0


@dataclass
class _DealerSpread:
    """One shuffled deck laid face-down for the dealer-selection draw.

    Transient application state rather than persisted domain state: it exists
    only between ``start_game`` and the moment a dealer is settled, and a tie
    replaces it wholesale.

    Attributes:
        cards: The 48 cards in spread order; an index is a position on the table.
        drawn: Which position each player took.
    """

    cards: list[Card]
    drawn: dict[str, int] = field(default_factory=dict)

    def cards_drawn(self) -> dict[str, Card]:
        """Return the card each player took, keyed by player."""
        return {player_id: self.cards[i] for player_id, i in self.drawn.items()}


class GameService(AdminPort, PlayerActionPort):
    """Application service — the use-case layer.

    Implements both AdminPort and PlayerActionPort. Every method follows
    the same pattern:
        1. Load game state.
        2. Execute use-case orchestration.
        3. Drain and broadcast all pending events.
        4. Save updated game state.

    The dealer-selection spread is tracked here because it is transient
    application-flow logic rather than persisted domain state.
    """

    def __init__(
        self,
        state: GameStatePort,
        notifier: NotificationPort,
        scheduler: SchedulerPort,
    ):
        """Wire the service to persistence, notification, and timing ports."""
        self._state = state
        self._notifier = notifier
        self._scheduler = scheduler
        self._spreads: dict[str, _DealerSpread] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dispatch(self, game: Game) -> None:
        """Deliver and clear all pending domain events for ``game``.

        Each event goes only to the players entitled to see it, so that
        private state never reaches a client that does not own it.
        """
        for event in game.pop_events():
            recipients = self._recipients(event)
            if recipients is None:
                self._notifier.broadcast(game.id, event)
            else:
                for player_id in recipients:
                    self._notifier.notify(player_id, event)

    @staticmethod
    def _recipients(event: GameEvent) -> list[str] | None:
        """Return who may see ``event``, or ``None`` when it is public.

        A dealt hand belongs to one player, and a pass is known only to the
        two partners who made it.  Everything else — bids, trump, exposed
        meld, played cards, scores — is public at a real table.
        """
        if isinstance(event, CardsDealt):
            return [event.player_id]
        if isinstance(event, CardsPassed):
            return [event.from_player_id, event.to_player_id]
        return None

    def _load_save(self, game_id: str, fn) -> None:
        """Load a game, mutate it via ``fn``, dispatch events, and persist it."""
        game = self._state.load(game_id)
        fn(game)
        self._dispatch(game)
        self._state.save(game)

    def _start_round(self, game: Game) -> None:
        """Create, deal, and announce a fresh round for the current dealer."""
        round_state = Round(
            dealer_id=game.dealer_id,
            player_order=game.player_order,
        )
        round_state.deal()
        game.begin_round(round_state)

        for pid in game.player_order:
            game.emit(CardsDealt(
                game_id=game.id,
                player_id=pid,
                cards=list(round_state.hand(pid)),
            ))

    @staticmethod
    def _player_team_map(game: Game) -> dict[str, str]:
        """Return a mapping from player ids to their team ids."""
        return {pid: game.team_id_for_player(pid) for pid in game.players}

    @staticmethod
    def _meld_scores(game: Game, round_state: Round) -> dict[str, int]:
        """Accumulate each team's meld from the totals recorded after the pass.

        Read from the round rather than recomputed, because by scoring time
        the hands are empty and would detect no meld at all.
        """
        totals: dict[str, int] = {}
        for pid in game.players:
            team_id = game.team_id_for_player(pid)
            totals[team_id] = totals.get(team_id, 0) + round_state.meld_total(pid)
        return totals

    @staticmethod
    def _check_winner(game: Game, bid_winner: str | None) -> str | None:
        """Determine whether a team has won the game after scoring."""
        over = [team for team in game.teams.values() if team.cumulative_score >= WINNING_SCORE]
        if not over:
            return None
        if len(over) > 1:
            return bid_winner and game.team_id_for_player(bid_winner)
        return over[0].id

    def _score_round(self, game: Game) -> None:
        """Score the completed round, emit events, and advance game state."""
        round_state = game.current_round
        player_team = self._player_team_map(game)
        tricks = round_state.tricks
        last_winner = tricks[-1].winner()

        trick_scores = score_tricks(tricks, last_winner, player_team)
        meld_scores = self._meld_scores(game, round_state)
        bid_team_id = game.team_id_for_player(round_state.bid_winner)
        net = resolve_round(trick_scores, meld_scores, bid_team_id, round_state.contract)

        for team_id, points in net.items():
            game.add_score(team_id, points)

        ns_score = game.teams.get(NS_TEAM_ID, Team(NS_TEAM_ID, "N/S")).cumulative_score
        ew_score = game.teams.get(EW_TEAM_ID, Team(EW_TEAM_ID, "E/W")).cumulative_score
        game.emit(RoundScored(game_id=game.id, ns_score=ns_score, ew_score=ew_score))

        winner = self._check_winner(game, round_state.bid_winner)
        if winner:
            game.set_finished()
            game.emit(GameOver(game_id=game.id, winning_team_id=winner))
            return

        game.rotate_dealer()
        self._start_round(game)

    # ------------------------------------------------------------------
    # AdminPort
    # ------------------------------------------------------------------

    def create_game(self) -> str:
        """Create, persist, and return a new empty game id."""
        game_id = str(uuid.uuid4())
        game = Game(game_id)
        self._state.save(game)
        return game_id

    def add_player(self, game_id: str, player: Player) -> None:
        """Add a player to an existing setup-phase game."""
        self._load_save(game_id, lambda g: g.add_player(player))

    def assign_teams(self, game_id: str, ns: Team, ew: Team) -> None:
        """Attach the two partnerships, whose ids are fixed by the seating."""
        if (ns.id, ew.id) != (NS_TEAM_ID, EW_TEAM_ID):
            raise ValueError(
                f"Team ids are fixed at {NS_TEAM_ID!r} and {EW_TEAM_ID!r}; "
                f"got {ns.id!r} and {ew.id!r}."
            )

        def _assign(g: Game) -> None:
            """Persist both team registrations on the aggregate."""
            g.add_team(ns)
            g.add_team(ew)

        self._load_save(game_id, _assign)

    def start_game(self, game_id: str) -> None:
        """Enter dealer selection and reset any pending draw state."""
        self._load_save(game_id, lambda g: g.start_dealer_selection())
        self._reset_spread(game_id)

    # ------------------------------------------------------------------
    # PlayerActionPort
    # ------------------------------------------------------------------

    def draw_for_deal(self, game_id: str, player_id: str, position: int) -> Card:
        """Take the card at ``position`` from the face-down spread.

        Each position may be taken by only one player, so the four drawn cards
        are necessarily four distinct cards from one deck (FR-12).
        """
        spread = self._spreads[game_id]
        if not 0 <= position < len(spread.cards):
            raise ValueError(f"Position {position} is not in the spread.")
        if player_id in spread.drawn:
            raise ValueError(f"{player_id} has already drawn.")
        if position in spread.drawn.values():
            raise ValueError(f"Position {position} has already been taken.")

        spread.drawn[player_id] = position
        card = spread.cards[position]

        game = self._state.load(game_id)
        if len(spread.drawn) == len(game.players):
            self._resolve_dealer_selection(game_id, spread)

        return card

    def _resolve_dealer_selection(self, game_id: str, spread: "_DealerSpread") -> None:
        """Settle a completed round of draws, redealing the spread on a tie."""
        winner = self._resolve_draw(spread.cards_drawn())
        if winner is None:
            # FR-14: a tie restarts the whole draw, all four players included.
            self._reset_spread(game_id)
            return

        self._spreads.pop(game_id, None)

        def _set_dealer_and_deal(g: Game) -> None:
            """Persist the dealer selection result and begin the round."""
            g.set_dealer(winner)
            g.emit(DealerSelected(game_id=g.id, dealer_player_id=winner))
            self._start_round(g)

        self._load_save(game_id, _set_dealer_and_deal)

    def spread_size(self, game_id: str) -> int:
        """Return how many positions the dealer-selection spread offers."""
        return len(self._spreads[game_id].cards)

    def positions_taken(self, game_id: str) -> set[int]:
        """Return the spread positions already claimed by a player."""
        return set(self._spreads[game_id].drawn.values())

    def _reset_spread(self, game_id: str) -> None:
        """Lay out a freshly shuffled face-down spread with nothing taken."""
        deck = Deck()
        deck.shuffle()
        self._spreads[game_id] = _DealerSpread(cards=list(deck))

    @staticmethod
    def _resolve_draw(draws: dict[str, Card]) -> str | None:
        """Return the unique highest draw winner or ``None`` on a tie.

        Rank alone decides it; suit never breaks a tie (FR-14).
        """
        max_value = max(c.rank.value for c in draws.values())
        winners = [pid for pid, c in draws.items() if c.rank.value == max_value]
        return winners[0] if len(winners) == 1 else None

    def place_bid(self, game_id: str, player_id: str, amount: int | None) -> None:
        """Record a player's bid or pass and publish the resulting event."""
        def _place_bid(g: Game) -> None:
            """Apply a bid to the current round and emit ``BidPlaced``."""
            g.current_round.place_bid(player_id, amount)
            g.emit(BidPlaced(game_id=g.id, player_id=player_id, amount=amount))

        self._load_save(game_id, _place_bid)

    def name_trump(self, game_id: str, player_id: str, suit: Suit) -> None:
        """Record the named trump suit for the active round."""
        def _name_trump(g: Game) -> None:
            """Apply the trump declaration and emit ``TrumpNamed``."""
            g.current_round.name_trump(player_id, suit)
            g.emit(TrumpNamed(game_id=g.id, suit=suit))

        self._load_save(game_id, _name_trump)

    def pass_cards(self, game_id: str, player_id: str, cards: list[Card]) -> None:
        """Submit a partner pass, exposing meld once both passes are in."""
        exchange_complete = False

        def _pass_cards(g: Game) -> None:
            """Apply the pass and announce meld when the exchange completes."""
            nonlocal exchange_complete
            round_state = g.current_round
            round_state.pass_cards(player_id, cards)
            g.emit(CardsPassed(
                game_id=g.id,
                from_player_id=player_id,
                to_player_id=round_state.partner_of(player_id),
                cards=list(cards),
            ))
            if round_state.phase == RoundPhase.MELDING:
                self._emit_meld_exposed(g)
                exchange_complete = True

        self._load_save(game_id, _pass_cards)

        # Started only after the save above has completed: the callback opens
        # its own load-mutate-save cycle, which must not nest inside this one.
        if exchange_complete:
            self._scheduler.call_later(
                MELD_DISPLAY_SECONDS,
                lambda: self._begin_trick_play(game_id),
            )

    @staticmethod
    def _emit_meld_exposed(game: Game) -> None:
        """Announce every player's recorded meld to the table."""
        round_state = game.current_round
        for pid in game.player_order:
            game.emit(MeldExposed(
                game_id=game.id,
                player_id=pid,
                units=round_state.meld(pid),
                total=round_state.meld_total(pid),
            ))

    def _begin_trick_play(self, game_id: str) -> None:
        """End the meld display and move the round into trick-taking."""
        self._load_save(game_id, lambda g: g.current_round.advance_to_playing())

    def play_card(self, game_id: str, player_id: str, card: Card) -> None:
        """Play a card into the current trick and score the round if needed."""
        def _play_card(g: Game) -> None:
            """Apply a trick play and handle trick-complete side effects."""
            winner_id = g.current_round.play_card(player_id, card)
            if winner_id is None:
                return

            last_trick = g.current_round.tricks[-1]
            g.emit(TrickCompleted(
                game_id=g.id,
                winner_player_id=winner_id,
                cards_played=last_trick.cards,
            ))
            if g.current_round.phase == RoundPhase.SCORING:
                self._score_round(g)

        self._load_save(game_id, _play_card)
