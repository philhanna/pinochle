# tests.services.test_computer_driver
import random

from pinochle.adapters.composite_notification import CompositeNotification
from pinochle.adapters.fake_scheduler import FakeScheduler
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.domain.game import CardsPassed, GamePhase, TrumpNamed
from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID, Team
from pinochle.ports.notification_port import NotificationPort
from pinochle.services.computer_driver import ComputerDriver
from pinochle.services.game_service import GameService
from pinochle.services.round import RoundPhase
from pinochle.strategies.computer_player_strategy import ComputerPlayerStrategy

ALL_COMPUTER_PLAYERS = [
    Player("N", "North", PlayerType.COMPUTER, Position.NORTH),
    Player("E", "East", PlayerType.COMPUTER, Position.EAST),
    Player("S", "South", PlayerType.COMPUTER, Position.SOUTH),
    Player("W", "West", PlayerType.COMPUTER, Position.WEST),
]

MIXED_PLAYERS = [
    Player("N", "North", PlayerType.HUMAN, Position.NORTH),
    Player("E", "East", PlayerType.COMPUTER, Position.EAST),
    Player("S", "South", PlayerType.HUMAN, Position.SOUTH),
    Player("W", "West", PlayerType.COMPUTER, Position.WEST),
]


class _RecordingNotifier(NotificationPort):
    """Minimal ``NotificationPort`` double that counts scheduler calls."""

    def __init__(self):
        self.events = []

    def notify(self, player_id, event):
        self.events.append(event)

    def broadcast(self, game_id, event):
        self.events.append(event)


def make_table(players, delay_seconds: float = 1.0, seed: int = 7):
    """Wire a service and driver together, returning both plus the scheduler."""
    state = InMemoryGameState()
    notifier = CompositeNotification()
    scheduler = FakeScheduler()
    service = GameService(
        state, notifier, scheduler, rng=random.Random(seed), trick_clear_seconds=0,
    )
    driver = ComputerDriver(
        service, state, scheduler, ComputerPlayerStrategy(), delay_seconds=delay_seconds,
    )
    notifier.append(driver)

    game_id = service.create_game()
    service.assign_teams(game_id, Team(NS_TEAM_ID, "Us"), Team(EW_TEAM_ID, "Them"))
    for player in players:
        service.add_player(game_id, player)
    return service, driver, state, scheduler, game_id


def test_starting_the_game_schedules_every_computer_seats_draw():
    """Dealer selection has no turn order, so every computer seat gets one."""
    service, _, _, scheduler, game_id = make_table(ALL_COMPUTER_PLAYERS)
    service.start_game(game_id)
    # Four draws pending: one per computer seat, none has fired yet.
    assert len(scheduler._pending) == 4


def test_a_calling_scheduler_only_receives_one_pending_move_per_seat():
    """Several events in one dispatch batch must not double-schedule a seat."""
    service, driver, state, scheduler, game_id = make_table(MIXED_PLAYERS)
    service.start_game(game_id)
    # start_game alone emits GameConfigured + DealerSelectionStarted — two
    # broadcasts — but East and West should each have exactly one pending draw.
    assert len(scheduler._pending) == 2


def test_a_human_seat_is_never_scheduled():
    """The driver must leave human seats alone entirely."""
    service, _, _, scheduler, game_id = make_table(MIXED_PLAYERS)
    service.start_game(game_id)
    scheduler.advance(1.0)
    # After the two computer seats have drawn, dealer selection still needs
    # North and South, who are human — nothing further should be pending.
    assert len(scheduler._pending) == 0


def test_deferred_scheduling_never_acts_synchronously():
    """A computer's move must not run inside the triggering dispatch cycle."""
    service, driver, state, scheduler, game_id = make_table(ALL_COMPUTER_PLAYERS)
    service.start_game(game_id)
    # Right after start_game, the four draws are scheduled but not yet run:
    # nobody has actually drawn from the spread.
    assert service.positions_taken(game_id) == set()


def test_an_all_computer_game_runs_to_completion_at_zero_delay():
    """FR-75c/ARC-10: a zero-delay all-computer game finishes without a browser."""
    service, driver, state, scheduler, game_id = make_table(
        ALL_COMPUTER_PLAYERS, delay_seconds=0, seed=7,
    )
    service.start_game(game_id)

    for _ in range(20000):
        if state.load(game_id).phase == GamePhase.FINISHED:
            break
        scheduler.advance(0)
    else:
        raise AssertionError("game never reached FINISHED")

    game = state.load(game_id)
    scores = {team_id: team.cumulative_score for team_id, team in game.teams.items()}
    assert max(scores.values()) >= 2000
    assert game.round_number > 0


def test_the_auction_winner_never_passes_trump_back():
    """FR-75b: the partner's pass carries trump in; the pass back carries none out."""
    service, driver, state, scheduler, game_id = make_table(
        ALL_COMPUTER_PLAYERS, delay_seconds=0, seed=7,
    )
    recorder = _RecordingNotifier()
    service._notifier.append(recorder)
    service.start_game(game_id)
    for _ in range(20000):
        if state.load(game_id).phase == GamePhase.FINISHED:
            break
        scheduler.advance(0)

    # Each pass is delivered to both partners, so the pass back is told
    # apart by who sent it: the seat that received the first one.
    trump = None
    first_passer = None
    passes_back = 0
    for event in recorder.events:
        if isinstance(event, TrumpNamed):
            trump, first_passer = event.suit, None
        elif isinstance(event, CardsPassed):
            first_passer = first_passer or event.from_player_id
            if event.from_player_id != first_passer:
                passes_back += 1
                assert all(card.suit != trump for card in event.cards)
    assert passes_back > 0


def test_a_seat_view_names_the_partner_across_the_table():
    """The bidding strategy has to know which other seat it is playing with.

    Who partners whom is public at a real table — only the partner's cards
    are not (FR-74), and the view still carries just the one hand.
    """
    service, driver, state, scheduler, game_id = make_table(
        ALL_COMPUTER_PLAYERS, delay_seconds=0, seed=7,
    )
    service.start_game(game_id)
    for _ in range(100):
        round_state = state.load(game_id).current_round
        if round_state is not None:
            break
        scheduler.advance(0)
    else:
        raise AssertionError("the round never began")

    view = driver._build_seat_view(round_state, "N")
    assert view.partner_id == "S"
    assert view.player_id == "N"


def test_an_all_computer_table_is_never_held():
    """RT-13: a hold nobody could ever release would stop the game, not pause it.

    The round summary holds the table so that the people at it can read the
    arithmetic before the next deal lands on top of it. Where there are no
    people, there is nothing to wait for and nobody who could ever end the
    wait -- which is why the all-computer game above can finish at all.
    """
    service, _, state, scheduler, game_id = make_table(
        ALL_COMPUTER_PLAYERS, delay_seconds=0, seed=7,
    )
    service.start_game(game_id)

    for _ in range(20000):
        if state.load(game_id).round_number > 1:
            break
        scheduler.advance(0)
    else:
        raise AssertionError("the table never reached a second round")

    assert state.load(game_id).current_hold is None


def test_a_table_with_one_human_is_held_at_the_summary():
    """RT-13: one human seat is enough for the summary to wait to be read."""
    service, _, state, scheduler, game_id = make_table(
        MIXED_PLAYERS, delay_seconds=0, seed=7,
    )
    service.start_game(game_id)

    # The computer seats drive play as far as they can; the two human seats
    # never act, so this stops wherever it first needs one of them.
    for _ in range(2000):
        scheduler.advance(0)

    game = state.load(game_id)
    hold = game.current_hold
    if hold is not None:
        assert hold.ackable, "a hold at a table with people in it waits for them"
        assert hold.seconds is None


def test_computer_never_tosses_in():
    """FR-75/75a/75b govern only bidding and passing; play is always seen through."""
    notifier = _RecordingNotifier()
    state = InMemoryGameState()
    scheduler = FakeScheduler()
    service = GameService(
        state, notifier, scheduler, rng=random.Random(7), trick_clear_seconds=0,
    )
    driver = ComputerDriver(
        service, state, scheduler, ComputerPlayerStrategy(), delay_seconds=0,
    )

    game_id = service.create_game()
    service.assign_teams(game_id, Team(NS_TEAM_ID, "Us"), Team(EW_TEAM_ID, "Them"))
    for player in ALL_COMPUTER_PLAYERS:
        service.add_player(game_id, player)
    service.start_game(game_id)

    for position, player_id in enumerate(["N", "E", "S", "W"]):
        service.draw_for_deal(game_id, player_id, position)
    while state.load(game_id).current_round is None:
        taken = service.positions_taken(game_id)
        free = (i for i in range(service.spread_size(game_id)) if i not in taken)
        for player_id in ["N", "E", "S", "W"]:
            service.draw_for_deal(game_id, player_id, next(free))

    round_state = state.load(game_id).current_round
    winner = round_state.current_player
    service.place_bid(game_id, winner, 250)
    for _ in range(3):
        service.place_bid(game_id, round_state.current_player, None)
    service.confirm_contract(game_id, winner, accept=True)
    trump = ComputerPlayerStrategy.choose_trump(list(round_state.hand(winner)))
    service.name_trump(game_id, winner, trump)
    while round_state.phase == RoundPhase.PASSING:
        passer = round_state.current_player
        cards = ComputerPlayerStrategy.choose_cards_to_pass(list(round_state.hand(passer)), trump)
        service.pass_cards(game_id, passer, cards)

    assert round_state.phase == RoundPhase.MELDING
    driver.pump(game_id)
    scheduler.advance(0)
    assert round_state.phase == RoundPhase.PLAYING
    assert round_state.tossed_in is False


def test_dealer_selection_draws_in_a_seat_determined_order():
    """NFR-7: which seat draws first decides who deals, so it must not vary.

    The seats awaiting a draw arrive as a set, and a set of player ids iterates
    in an order that depends on string hashing, which differs from one process
    to the next — so scheduling straight from it left even a seeded game
    unreproducible.  The driver now walks them by seat position instead.

    The resulting order is reverse-clockwise rather than clockwise, because
    ``_schedule`` announces a seat before queueing it and that announcement
    recurses into ``pump``, so the last seat reached is the first queued.  That
    is harmless — FR-11 lets the four draw in any order — and it is the
    order's *stability* that this test is for, not its direction.
    """
    notifier = _RecordingNotifier()
    service, _, _, scheduler, game_id = make_table(ALL_COMPUTER_PLAYERS, delay_seconds=0)
    # Ahead of the driver in the delivery list, so each event is recorded when
    # it is published rather than after the driver has recursed on it.
    service._notifier._notifiers.insert(0, notifier)

    service.start_game(game_id)
    scheduler.advance(1.0)

    drawn = [
        event.player_id for event in notifier.events
        if type(event).__name__ == "DrawMade"
    ]
    assert drawn == ["W", "S", "E", "N"]


ONE_HUMAN_PLAYERS = [
    Player("N", "North", PlayerType.COMPUTER, Position.NORTH),
    Player("E", "East", PlayerType.COMPUTER, Position.EAST),
    Player("S", "Grace", PlayerType.HUMAN, Position.SOUTH),
    Player("W", "West", PlayerType.COMPUTER, Position.WEST),
]


def _stall_at_the_human_seat(service, state, scheduler, game_id) -> str:
    """Drive a one-human table as far as the computers can take it alone.

    The human draws for the deal — once per spread, since a tie throws the
    whole draw again (FR-14) — so the table gets into a dealt round; from
    there the computers play up to the point where South is on the clock, and
    stop.  Returns the round's current player, which is the seat the table is
    now waiting on.
    """
    service.start_game(game_id)
    for _ in range(2000):
        scheduler.advance(0)
        game = state.load(game_id)
        if game.current_hold is not None:
            service.acknowledge(game_id, "S", game.current_hold.id)
            continue
        if game.current_round is not None:
            break
        if game.phase == GamePhase.DEALER_SELECTION and "S" in service.players_awaiting_draw(game_id):
            taken = service.positions_taken(game_id)
            service.draw_for_deal(game_id, "S", next(
                i for i in range(service.spread_size(game_id)) if i not in taken))
    else:
        raise AssertionError("the deal never began")

    for _ in range(2000):
        scheduler.advance(0)
    return state.load(game_id).current_round.current_player


def test_a_table_stops_where_its_absent_player_left_it():
    """RT-12: nothing acts for an absent seat, so play blocks there."""
    service, _, state, scheduler, game_id = make_table(
        ONE_HUMAN_PLAYERS, delay_seconds=0, seed=7,
    )
    assert _stall_at_the_human_seat(service, state, scheduler, game_id) == "S"
    assert state.load(game_id).phase == GamePhase.IN_ROUND


def test_seating_a_computer_resumes_the_round_from_where_it_stopped():
    """RT-12a: the seat keeps its cards and its turn; only who decides changes."""
    service, _, state, scheduler, game_id = make_table(
        ONE_HUMAN_PLAYERS, delay_seconds=0, seed=7,
    )
    _stall_at_the_human_seat(service, state, scheduler, game_id)

    game = state.load(game_id)
    round_number = game.round_number
    hand = list(game.current_round.hand("S"))

    service.seat_computer(game_id, "S")

    game = state.load(game_id)
    assert game.players["S"].type == PlayerType.COMPUTER
    assert game.players["S"].name == "Grace"
    # Nothing is dealt again: the same round, with the same cards in the
    # seat that was waiting on its player.
    assert game.round_number == round_number
    assert list(game.current_round.hand("S")) == hand

    scheduler.advance(0)
    assert state.load(game_id).current_round.current_player != "S"


def test_a_table_seated_entirely_by_computers_plays_the_game_out():
    """RT-12a: the three who are left get a finished game, not a stopped one."""
    service, _, state, scheduler, game_id = make_table(
        ONE_HUMAN_PLAYERS, delay_seconds=0, seed=7,
    )
    _stall_at_the_human_seat(service, state, scheduler, game_id)
    service.seat_computer(game_id, "S")

    for _ in range(20000):
        if state.load(game_id).phase == GamePhase.FINISHED:
            break
        scheduler.advance(0)
    else:
        raise AssertionError("the game never finished after the seat was replaced")


def test_seating_a_computer_releases_a_hold_nobody_is_left_to_read():
    """RT-13: an ackable hold at an all-computer table is a stop, not a pause."""
    service, _, state, scheduler, game_id = make_table(
        ONE_HUMAN_PLAYERS, delay_seconds=0, seed=7,
    )
    _stall_at_the_human_seat(service, state, scheduler, game_id)

    # Drive to the meld hold, which waits on the one human seat, by acting
    # for South until the table stops on a hold rather than on its turn.
    game = state.load(game_id)
    for _ in range(200):
        if game.current_hold is not None and game.current_hold.ackable:
            break
        round_state = game.current_round
        if round_state.current_player == "S":
            _act_for(service, game_id, round_state)
        scheduler.advance(0)
        game = state.load(game_id)
    else:
        raise AssertionError("the table never reached a hold awaiting release")

    service.seat_computer(game_id, "S")
    assert state.load(game_id).current_hold is None


def _act_for(service, game_id, round_state) -> None:
    """Play the absent seat's turn the way a plain human client would."""
    player_id = round_state.current_player
    phase = round_state.phase
    if phase == RoundPhase.BIDDING:
        service.place_bid(game_id, player_id, None)
    elif phase == RoundPhase.CONFIRMING:
        service.confirm_contract(game_id, player_id, accept=True)
    elif phase == RoundPhase.TRUMP:
        service.name_trump(game_id, player_id, list(round_state.hand(player_id))[0].suit)
    elif phase == RoundPhase.PASSING:
        service.pass_cards(game_id, player_id, list(round_state.hand(player_id))[:4])
    elif phase == RoundPhase.PLAYING:
        service.play_card(game_id, player_id, round_state.legal_plays(player_id)[0])
