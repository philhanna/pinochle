# tests.adapters.test_sse_notification
from pinochle.adapters.sse_notification import SseNotification
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
