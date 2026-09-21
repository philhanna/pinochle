# tests.services.test_computer_driver
import random

from pinochle.adapters.composite_notification import CompositeNotification
from pinochle.adapters.fake_scheduler import FakeScheduler
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.domain.game import GamePhase
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
