# pinochle.services.computer_driver
from pinochle.domain.game import GameEvent, GamePhase
from pinochle.domain.player import PlayerType
from pinochle.ports.game_state_port import GameStatePort
from pinochle.ports.notification_port import NotificationPort
from pinochle.ports.player_action_port import PlayerActionPort
from pinochle.ports.scheduler_port import SchedulerPort
from pinochle.services.game_service import GameService
from pinochle.services.round import Round, RoundPhase
from pinochle.services.seat_view import SeatView
from pinochle.strategies.computer_player_strategy import ComputerPlayerStrategy


class ComputerDriver(PlayerActionPort, NotificationPort):
    """Drives every computer seat, indistinguishably from a human client.

    Plays two roles at once (design.md §7.1):

    - A decorator over ``PlayerActionPort``: every method delegates straight
      to the wrapped ``GameService``, so the web layer depends only on the
      port and never has to know a seat is a computer.
    - A ``NotificationPort`` observer: appended to the composite notifier,
      it sees every event the service publishes, including ones from the
      service's own scheduler callbacks (``TrickCleared``) that no decorator
      could intercept.  After any event, it looks at whose turn it is next.
    """

    def __init__(
        self,
        service: GameService,
        state: GameStatePort,
        scheduler: SchedulerPort,
        strategy: ComputerPlayerStrategy,
        delay_seconds: float = 1.0,
    ):
        """Wire the driver to the service it decorates and observes.

        ``state`` is read directly (not through ``service``) so ``_act`` can
        build a ``SeatView`` without needing a new read method on
        ``GameService`` for every field a strategy might want.
        """
        self._service = service
        self._state = state
        self._scheduler = scheduler
        self._strategy = strategy
        self._delay_seconds = delay_seconds
        self._pending: set[tuple[str, str]] = set()

    # ------------------------------------------------------------------
    # NotificationPort — observes every event to know when to pump
    # ------------------------------------------------------------------

    def notify(self, player_id: str, event: GameEvent) -> None:
        """React to a private event exactly like a public one: pump the game."""
        self.pump(event.game_id)

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """React to a public event by pumping the game."""
        self.pump(game_id)

    # ------------------------------------------------------------------
    # The pump
    # ------------------------------------------------------------------

    def pump(self, game_id: str) -> None:
        """Schedule a computer move for whoever is due one, coalescing repeats.

        Dealer selection has no single "current player" — any player who
        hasn't drawn yet may draw at any time — so every computer seat still
        awaiting a draw is scheduled.  Every later phase has exactly one
        seat on the clock, from ``Round.current_player``.
        """
        game = self._state.load(game_id)
        if game.phase == GamePhase.DEALER_SELECTION:
            for seat in self._service.players_awaiting_draw(game_id):
                if game.players[seat].type == PlayerType.COMPUTER:
                    self._schedule(game_id, seat)
            return

        seat = self._current_actor(game)
        if seat is None or game.players[seat].type != PlayerType.COMPUTER:
            return
        self._schedule(game_id, seat)

    def _schedule(self, game_id: str, seat: str) -> None:
        """Schedule one seat's deferred move, unless one is already pending.

        One load/dispatch/save cycle can publish several events (four
        ``CardsDealt``, then four ``MeldExposed``); without this the same
        seat could be scheduled to act twice for what is really one turn.
        """
        key = (game_id, seat)
        if key in self._pending:
            return
        self._pending.add(key)
        self._service.note_seat_thinking(game_id, seat)
        self._scheduler.call_later(self._delay_seconds, lambda: self._act(game_id, seat))

    @staticmethod
    def _current_actor(game) -> str | None:
        """Return whose turn it is, or ``None`` if nobody is (design.md §7.2)."""
        if game.phase != GamePhase.IN_ROUND:
            return None
        round_state = game.current_round
        return round_state.current_player if round_state else None

    def _act(self, game_id: str, seat: str) -> None:
        """Decide and submit the move deferred by ``pump``.

        Deferral is mandatory (design.md §7.2): this must never run
        synchronously inside ``_dispatch``, which happens *before*
        ``GameService`` saves the game — an immediate call here would load a
        stale aggregate and then be overwritten by the outer save.
        ``AsyncioScheduler`` guarantees at least one tick of deferral even at
        a delay of zero, which is what makes this safe.
        """
        self._pending.discard((game_id, seat))
        game = self._state.load(game_id)

        if game.phase == GamePhase.DEALER_SELECTION:
            # Re-checked fresh rather than trusted from when this was
            # scheduled: a tie may have reset the spread, or this seat may
            # already have drawn from it.
            if seat not in self._service.players_awaiting_draw(game_id):
                return
            position = self._strategy.choose_draw_position(
                self._service.positions_taken(game_id),
                self._service.spread_size(game_id),
            )
            self._service.draw_for_deal(game_id, seat, position)
            return

        # The state may have moved on since the delay was scheduled (the
        # round could have ended, or — defensively — someone else could
        # already hold the turn); re-validate rather than trust the past.
        if self._current_actor(game) != seat:
            return

        round_state = game.current_round
        view = self._build_seat_view(round_state, seat)
        phase = round_state.phase

        if phase == RoundPhase.BIDDING:
            amount = self._strategy.choose_bid(view.hand, view.current_high_bid)
            self._service.place_bid(game_id, seat, amount)
        elif phase == RoundPhase.CONFIRMING:
            # A computer's own conservative estimate already decided
            # whether the bid was worth making; it never backs out now.
            self._service.confirm_contract(game_id, seat, accept=True)
        elif phase == RoundPhase.TRUMP:
            suit = self._strategy.choose_trump(view.hand)
            self._service.name_trump(game_id, seat, suit)
        elif phase == RoundPhase.PASSING:
            cards = self._strategy.choose_cards_to_pass(view.hand, view.trump)
            self._service.pass_cards(game_id, seat, cards)
        elif phase == RoundPhase.MELDING:
            # FR-75/75a/75b govern only bidding and passing; a computer
            # always plays the contract out rather than tossing it in.
            self._service.begin_play(game_id, seat)
        elif phase == RoundPhase.PLAYING:
            card = self._strategy.choose_play(view.legal_plays)
            self._service.play_card(game_id, seat, card)

    @staticmethod
    def _build_seat_view(round_state: Round, player_id: str) -> SeatView:
        """Build the seat's own private view (FR-74) for the strategy to act on."""
        return SeatView(
            player_id=player_id,
            hand=list(round_state.hand(player_id)),
            bid_history=round_state.bid_history,
            current_high_bid=round_state.current_high_bid,
            trump=round_state.trump,
            cards_on_table=round_state.current_trick_cards,
            exposed_meld=round_state.all_meld(),
            legal_plays=(
                round_state.legal_plays(player_id)
                if round_state.phase == RoundPhase.PLAYING
                else []
            ),
        )

    # ------------------------------------------------------------------
    # PlayerActionPort — delegates every method to the wrapped service
    # ------------------------------------------------------------------

    def draw_for_deal(self, game_id, player_id, position):
        """Delegate to the wrapped service."""
        return self._service.draw_for_deal(game_id, player_id, position)

    def place_bid(self, game_id, player_id, amount):
        """Delegate to the wrapped service."""
        return self._service.place_bid(game_id, player_id, amount)

    def name_trump(self, game_id, player_id, suit):
        """Delegate to the wrapped service."""
        return self._service.name_trump(game_id, player_id, suit)

    def pass_cards(self, game_id, player_id, cards):
        """Delegate to the wrapped service."""
        return self._service.pass_cards(game_id, player_id, cards)

    def play_card(self, game_id, player_id, card):
        """Delegate to the wrapped service."""
        return self._service.play_card(game_id, player_id, card)

    def confirm_contract(self, game_id, player_id, accept):
        """Delegate to the wrapped service."""
        return self._service.confirm_contract(game_id, player_id, accept)

    def begin_play(self, game_id, player_id):
        """Delegate to the wrapped service."""
        return self._service.begin_play(game_id, player_id)

    def toss_in(self, game_id, player_id):
        """Delegate to the wrapped service."""
        return self._service.toss_in(game_id, player_id)
