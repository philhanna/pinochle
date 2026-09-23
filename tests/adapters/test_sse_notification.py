# tests.adapters.test_sse_notification
from pinochle.adapters.sse_notification import STREAM_CLOSED, SseNotification
from pinochle.domain.game import BidPlaced, DealerSelected
from tests.ports.test_notification_port import run_contract


def test_contract():
    """Verify the SSE hub satisfies the shared notification contract."""
    run_contract(SseNotification())


async def test_a_seat_with_two_queues_gets_a_notify_on_both():
    """FR-10c: several open connections for one seat all see a private event."""
    hub = SseNotification()
    q1 = hub.subscribe("g1", "N")
    q2 = hub.subscribe("g1", "N")

    event = BidPlaced(game_id="g1", player_id="N", amount=250, current_high=250)
    hub.notify("N", event)

    assert q1.get_nowait() == (1, event)
    assert q2.get_nowait() == (1, event)


async def test_broadcast_reaches_the_admin_queue_but_notify_does_not():
    """§6.3: the admin console sees exactly the broadcasts, never a private notify."""
    hub = SseNotification()
    admin_q = hub.subscribe_admin("g1")
    seat_q = hub.subscribe("g1", "N")

    private = BidPlaced(game_id="g1", player_id="N", amount=250, current_high=250)
    hub.notify("N", private)
    assert admin_q.empty()
    assert seat_q.get_nowait() == (1, private)

    public = DealerSelected(game_id="g1", dealer_player_id="N")
    hub.broadcast("g1", public)
    assert admin_q.get_nowait() == (2, public)
    assert seat_q.get_nowait() == (2, public)


async def test_broadcast_reaches_every_seat_in_the_game():
    """A broadcast delivers to every seat's queues, not just one."""
    hub = SseNotification()
    n_q = hub.subscribe("g1", "N")
    e_q = hub.subscribe("g1", "E")

    event = DealerSelected(game_id="g1", dealer_player_id="N")
    hub.broadcast("g1", event)

    assert n_q.get_nowait() == (1, event)
    assert e_q.get_nowait() == (1, event)


async def test_sequence_numbers_are_shared_across_notify_and_broadcast():
    """§6.4: ``id:`` reflects one gapless order for everything in a game."""
    hub = SseNotification()
    queue = hub.subscribe("g1", "N")

    hub.notify("N", BidPlaced(game_id="g1", player_id="N", amount=250, current_high=250))
    hub.broadcast("g1", DealerSelected(game_id="g1", dealer_player_id="N"))
    hub.notify("N", BidPlaced(game_id="g1", player_id="N", amount=None, current_high=250))

    seqs = [queue.get_nowait()[0] for _ in range(3)]
    assert seqs == [1, 2, 3]


async def test_unsubscribe_stops_further_delivery():
    """A closed connection's queue must not keep receiving events."""
    hub = SseNotification()
    queue = hub.subscribe("g1", "N")
    hub.unsubscribe("g1", "N", queue)

    hub.broadcast("g1", DealerSelected(game_id="g1", dealer_player_id="N"))
    assert queue.empty()


async def test_seats_connected_reflects_open_subscriptions():
    """FR-10b: the admin console can tell which human seats have joined."""
    hub = SseNotification()
    assert hub.seats_connected("g1") == set()

    queue = hub.subscribe("g1", "N")
    assert hub.seats_connected("g1") == {"N"}

    hub.unsubscribe("g1", "N", queue)
    assert hub.seats_connected("g1") == set()


async def test_a_full_queue_is_dropped_rather_than_blocking():
    """§6.8: a hopelessly behind subscriber is dropped, not left to jam the hub."""
    hub = SseNotification(queue_maxsize=1)
    hub.subscribe("g1", "N")
    hub.notify("N", DealerSelected(game_id="g1", dealer_player_id="N"))  # fills it

    hub.notify("N", DealerSelected(game_id="g1", dealer_player_id="N"))  # would block
    assert hub.seats_connected("g1") == set()


def test_history_replays_what_a_seat_missed_in_order():
    """RT-5a: a dropped seat gets back exactly the frames it did not see."""
    hub = SseNotification()
    first = DealerSelected(game_id="g1", dealer_player_id="N")
    second = BidPlaced(game_id="g1", player_id="N", amount=250, current_high=250)
    third = BidPlaced(game_id="g1", player_id="E", amount=260, current_high=260)
    hub.broadcast("g1", first)
    hub.broadcast("g1", second)
    hub.broadcast("g1", third)

    missed, whole = hub.history_since("g1", "N", after_seq=1)

    assert whole is True
    assert missed == [(2, second), (3, third)]


def test_history_never_replays_another_seat_s_private_event():
    """NFR-6: resuming is not a way round the filter a live stream applies."""
    hub = SseNotification()
    mine = BidPlaced(game_id="g1", player_id="N", amount=250, current_high=250)
    theirs = BidPlaced(game_id="g1", player_id="E", amount=260, current_high=260)
    public = DealerSelected(game_id="g1", dealer_player_id="N")
    hub.notify("N", mine)
    hub.notify("E", theirs)
    hub.broadcast("g1", public)

    missed, _ = hub.history_since("g1", "N", after_seq=0)

    assert missed == [(1, mine), (3, public)]


def test_history_reports_a_hole_it_cannot_fill():
    """A seat asking from further back than the buffer holds is told so."""
    hub = SseNotification(history_maxlen=2)
    for amount in (250, 260, 270):
        hub.broadcast("g1", BidPlaced(game_id="g1", player_id="N", amount=amount, current_high=amount))

    # The buffer now starts at seq 2, so a seat resuming after seq 0 has a hole
    # between what it last saw and what can still be replayed.
    assert hub.history_since("g1", "N", after_seq=0)[1] is False
    assert hub.history_since("g1", "N", after_seq=1)[1] is True


def test_history_for_a_game_this_process_never_saw():
    """A fresh stream is vacuously whole; a resume into nothing is not."""
    hub = SseNotification()

    assert hub.history_since("g1", "N", after_seq=0) == ([], True)
    assert hub.history_since("g1", "N", after_seq=7) == ([], False)


async def test_closing_a_seat_ends_every_stream_it_holds_open():
    """RT-12a: an unlinked seat's connections are told to stop, not just dropped."""
    hub = SseNotification()
    first = hub.subscribe("g1", "N")
    second = hub.subscribe("g1", "N")
    other = hub.subscribe("g1", "E")

    assert hub.close_seat("g1", "N") == 2

    assert first.get_nowait() is STREAM_CLOSED
    assert second.get_nowait() is STREAM_CLOSED
    assert other.empty()
    assert hub.seats_connected("g1") == {"E"}


async def test_a_closed_seat_receives_nothing_further():
    """The seat is gone from the fan-out, so later events pass it by."""
    hub = SseNotification()
    queue = hub.subscribe("g1", "N")
    hub.close_seat("g1", "N")
    queue.get_nowait()

    hub.broadcast("g1", DealerSelected(game_id="g1", dealer_player_id="N"))

    assert queue.empty()


async def test_closing_a_seat_whose_client_stopped_reading_still_ends_it():
    """§6.8: a full queue is precisely the client that most needs ending."""
    hub = SseNotification(queue_maxsize=2)
    queue = hub.subscribe("g1", "N")
    for _ in range(2):
        hub.broadcast("g1", DealerSelected(game_id="g1", dealer_player_id="N"))
    assert queue.full()

    hub.close_seat("g1", "N")

    frames = [queue.get_nowait() for _ in range(queue.qsize())]
    assert frames[-1] is STREAM_CLOSED


async def test_closing_a_seat_that_has_no_streams_is_harmless():
    """Unlinking a player who had already gone changes nothing and says so."""
    hub = SseNotification()
    assert hub.close_seat("g1", "N") == 0
