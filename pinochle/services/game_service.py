# pinochle.services.game_service
import uuid
from dataclasses import dataclass, field

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.deck import Deck
from pinochle.domain.cards.suit import Suit
from pinochle.domain.game import (
    BidPlaced,
    CardPlayed,
    CardsDealt,
    CardsPassed,
    ContractOffered,
    ContractTossedIn,
    DealerSelected,
    DealerSelectionStarted,
    DrawMade,
    DrawTied,
    Game,
    GameConfigured,
    GameEvent,
    GamePhase,
    GameOver,
    MeldExposed,
    PlayBegun,
    RoundAbandoned,
    RoundScored,
    RoundStarted,
    TrickCleared,
    TrickCompleted,
    TrumpNamed,
)
from pinochle.domain.player import Player
from pinochle.domain.scoring import (
    LAST_TRICK_BONUS,
    WINNING_SCORE,
    resolve_round,
    resolve_toss_in,
    score_card_points,
)
from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID, Team
from pinochle.domain.team_round_score import TeamRoundScore
from pinochle.ports.admin_port import AdminPort
from pinochle.ports.game_state_port import GameStatePort
from pinochle.ports.notification_port import NotificationPort
from pinochle.ports.player_action_port import PlayerActionPort
from pinochle.ports.scheduler_port import SchedulerPort
from pinochle.services.round import Round, RoundPhase

# How long a completed trick stays on the table before it is swept to the
# winner.  Server-owned, per RT-8, so all four clients see the same thing.
TRICK_CLEAR_SECONDS = 1.5


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
        game.emit(RoundStarted(
            game_id=game.id,
            round_number=game.round_number,
            dealer_player_id=game.dealer_id,
        ))

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
        meld_scores = self._meld_scores(game, round_state)
        bid_team_id = game.team_id_for_player(round_state.bid_winner)
        card_points, bonus = self._trick_points(game, round_state)

        if round_state.tossed_in:
            net = resolve_toss_in(meld_scores, bid_team_id, round_state.contract)
        else:
            trick_scores = {
                team_id: card_points.get(team_id, 0) + bonus.get(team_id, 0)
                for team_id in game.teams
            }
            net = resolve_round(
                trick_scores, meld_scores, bid_team_id, round_state.contract)

        for team_id, points in net.items():
            game.add_score(team_id, points)

        game.emit(self._round_scored(
            game,
            round_state,
            bid_team_id=bid_team_id,
            meld_scores=meld_scores,
            card_points=card_points,
            bonus=bonus,
            net=net,
        ))

        winner = self._check_winner(game, round_state.bid_winner)
        if winner:
            game.set_finished()
            game.emit(GameOver(
                game_id=game.id,
                winning_team_id=winner,
                ns_score=self._team_score(game, NS_TEAM_ID),
                ew_score=self._team_score(game, EW_TEAM_ID),
            ))
            return

        game.rotate_dealer()
        self._start_round(game)

    def _trick_points(
        self, game: Game, round_state: Round
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Return each team's captured card points and last-trick bonus.

        The two are kept apart because FR-66 reports them as separate figures.
        A tossed-in round played no trick at all (FR-50c), so both are empty.
        """
        if round_state.tossed_in:
            return {}, {}
        tricks = round_state.tricks
        team_map = self._player_team_map(game)
        last_team = team_map[tricks[-1].winner()]
        return (
            score_card_points(tricks, team_map),
            {last_team: LAST_TRICK_BONUS},
        )

    @staticmethod
    def _round_scored(
        game: Game,
        round_state: Round,
        *,
        bid_team_id: str,
        meld_scores: dict[str, int],
        card_points: dict[str, int],
        bonus: dict[str, int],
        net: dict[str, int],
    ) -> RoundScored:
        """Build the round summary FR-66 requires be shown to both teams."""
        lines = {
            team_id: TeamRoundScore(
                team_id=team_id,
                meld=meld_scores.get(team_id, 0),
                card_points=card_points.get(team_id, 0),
                last_trick_bonus=bonus.get(team_id, 0),
                round_total=(meld_scores.get(team_id, 0)
                             + card_points.get(team_id, 0)
                             + bonus.get(team_id, 0)),
                points_applied=net.get(team_id, 0),
                cumulative_score=team.cumulative_score,
            )
            for team_id, team in game.teams.items()
        }
        return RoundScored(
            game_id=game.id,
            round_number=game.round_number,
            bid_team_id=bid_team_id,
            bid_winner_player_id=round_state.bid_winner,
            contract=round_state.contract,
            made_contract=(not round_state.tossed_in
                           and lines[bid_team_id].round_total >= round_state.contract),
            tossed_in=round_state.tossed_in,
            teams=list(lines.values()),
        )

    @staticmethod
    def _team_score(game: Game, team_id: str) -> int:
        """Return a team's cumulative score, or zero if it was never registered."""
        team = game.teams.get(team_id)
        return team.cumulative_score if team else 0

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
        """Enter dealer selection, laying out the first face-down spread.

        The spread is laid before the events are published, so that
        ``DealerSelectionStarted`` can state how many positions it offers.
        """
        self._reset_spread(game_id)

        def _start(g: Game) -> None:
            """Close setup and announce the fixed table and the spread."""
            g.start_dealer_selection()
            g.emit(GameConfigured(
                game_id=g.id,
                players=[g.players[pid] for pid in g.player_order],
                teams=list(g.teams.values()),
                winning_score=WINNING_SCORE,
            ))
            g.emit(DealerSelectionStarted(
                game_id=g.id,
                spread_size=self.spread_size(g.id),
            ))

        self._load_save(game_id, _start)

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
        self._load_save(game_id, lambda g: g.emit(DrawMade(
            game_id=g.id,
            player_id=player_id,
            position=position,
            card=card,
        )))

        game = self._state.load(game_id)
        if len(spread.drawn) == len(game.players):
            self._resolve_dealer_selection(game_id, spread)

        return card

    def _resolve_dealer_selection(self, game_id: str, spread: "_DealerSpread") -> None:
        """Settle a completed round of draws, redealing the spread on a tie."""
        drawn = spread.cards_drawn()
        winner = self._resolve_draw(drawn)
        if winner is None:
            # FR-14: a tie restarts the whole draw, all four players included.
            self._reset_spread(game_id)

            def _announce_tie(g: Game) -> None:
                """Show the tied draw, then the spread replacing it."""
                g.emit(DrawTied(game_id=g.id, cards=drawn))
                g.emit(DealerSelectionStarted(
                    game_id=g.id,
                    spread_size=self.spread_size(g.id),
                ))

            self._load_save(game_id, _announce_tie)
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
            if g.current_round.phase == RoundPhase.ABANDONED:
                self._abandon_round(g, declined_by=None)
            elif g.current_round.phase == RoundPhase.CONFIRMING:
                # FR-32: the other three learn why the auction has paused.
                g.emit(ContractOffered(
                    game_id=g.id,
                    player_id=g.current_round.bid_winner,
                    amount=g.current_round.contract,
                ))

        self._load_save(game_id, _place_bid)

    def confirm_contract(self, game_id: str, player_id: str, accept: bool) -> None:
        """Take or decline a contract nobody bid against."""
        def _confirm(g: Game) -> None:
            """Apply the lone bidder's decision and abandon the round if declined."""
            g.current_round.confirm_contract(player_id, accept)
            if g.current_round.phase == RoundPhase.ABANDONED:
                self._abandon_round(g, declined_by=player_id)

        self._load_save(game_id, _confirm)

    def _abandon_round(self, game: Game, declined_by: str | None) -> None:
        """End a round before play and deal the next one, scores untouched."""
        game.emit(RoundAbandoned(game_id=game.id, declined_by=declined_by))
        game.rotate_dealer()
        self._start_round(game)

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

    def begin_play(self, game_id: str, player_id: str) -> None:
        """Start trick play once the auction winner has read the exposed meld."""
        def _begin_play(g: Game) -> None:
            """End the meld display and announce the opening lead."""
            g.current_round.begin_play(player_id)
            g.emit(PlayBegun(game_id=g.id, leader_player_id=player_id))

        self._load_save(game_id, _begin_play)

    def toss_in(self, game_id: str, player_id: str) -> None:
        """Concede the contract without playing it out, and score the round."""
        def _toss_in(g: Game) -> None:
            """Give up the contract and settle the round immediately."""
            g.current_round.toss_in(player_id)
            g.emit(ContractTossedIn(game_id=g.id, player_id=player_id))
            self._score_round(g)

        self._load_save(game_id, _toss_in)

    def play_card(self, game_id: str, player_id: str, card: Card) -> None:
        """Play a card into the current trick, holding a completed one on the table."""
        trick_complete = False

        def _play_card(g: Game) -> None:
            """Apply a trick play and announce a completed trick."""
            nonlocal trick_complete
            winner_id = g.current_round.play_card(player_id, card)
            g.emit(CardPlayed(game_id=g.id, player_id=player_id, card=card))
            if winner_id is None:
                return
            g.emit(TrickCompleted(
                game_id=g.id,
                winner_player_id=winner_id,
                cards_played=g.current_round.current_trick_cards,
            ))
            trick_complete = True

        self._load_save(game_id, _play_card)

        # Started only after the save above, so the callback's own
        # load-mutate-save cycle does not nest inside this one.
        if trick_complete:
            self._scheduler.call_later(
                TRICK_CLEAR_SECONDS,
                lambda: self._clear_trick(game_id),
            )

    def _clear_trick(self, game_id: str) -> None:
        """Sweep the completed trick to its winner and score the round if it ended."""
        def _clear(g: Game) -> None:
            """Collect the trick and settle the round once the hands are empty."""
            round_state = g.current_round
            winner_id = round_state.clear_trick()
            round_over = round_state.phase == RoundPhase.SCORING
            g.emit(TrickCleared(
                game_id=g.id,
                winner_player_id=winner_id,
                next_leader_player_id=None if round_over else winner_id,
            ))
            if round_over:
                self._score_round(g)

        self._load_save(game_id, _clear)
