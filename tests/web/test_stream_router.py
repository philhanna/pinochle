# tests.web.test_stream_router
import asyncio
import json

from starlette.requests import Request

from pinochle.adapters.sse_notification import SseNotification
from pinochle.web.routers import admin as admin_router
from pinochle.web.routers import stream as stream_router
from tests.web.conftest import seat_players


def _request(last_event_id: str | None = None) -> Request:
    """Build a bare GET request, optionally resuming from ``last_event_id``.

    That header is what ``EventSource`` sends back when it reconnects, so it
    is the only part of the request the stream route reads.
    """
    headers = [] if last_event_id is None else [(b"last-event-id", last_event_id.encode())]
    return Request({"type": "http", "method": "GET", "headers": headers})


async def _anext(iterator, timeout: float = 1.0):
    """Pull the next frame from a stream generator, failing fast if it hangs."""
    return await asyncio.wait_for(iterator.__anext__(), timeout=timeout)


def _frame_type(raw: str) -> str:
    """Return the ``event:`` name from a raw SSE frame."""
    for line in raw.splitlines():
        if line.startswith("event: "):
            return line[len("event: "):]
    raise AssertionError(f"no event: line in frame: {raw!r}")


def _seq(raw: str) -> int:
    """Return the sequence number from a raw SSE frame's ``id:`` line."""
    for line in raw.splitlines():
        if line.startswith("id: "):
            return int(line[len("id: "):])
    raise AssertionError(f"no id: line in frame: {raw!r}")


def _payload(raw: str) -> dict:
    """Return the JSON payload embedded in a raw SSE frame's data: line."""
    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: "):])["payload"]
    raise AssertionError(f"no data: line in frame: {raw!r}")


async def _drain(iterator, timeout: float = 0.2) -> list[str]:
    """Return the names of every frame already waiting, stopping at the first lull."""
    names = []
    try:
        while True:
            names.append(_frame_type(await _anext(iterator, timeout=timeout)))
    except asyncio.TimeoutError:
        pass
    finally:
        await iterator.aclose()
    return names


async def test_player_stream_opens_with_retry_then_stream_started(container):
    """§6.2: the connection sets its retry interval, then identifies the seat."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)

    response = await stream_router.player_stream(
        game_id, _request(), container=container, player_id="p-north",
    )
    it = response.body_iterator
    assert await _anext(it) == "retry: 2000\n\n"
    started = await _anext(it)
    assert _frame_type(started) == "stream_started"
    assert _payload(started)["seat"] == "NORTH"
    assert _payload(started)["player_id"] == "p-north"
    await it.aclose()


async def test_broadcasts_reach_the_subscribed_seat(container):
    """A public event published after the stream opens should be relayed."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)

    response = await stream_router.player_stream(
        game_id, _request(), container=container, player_id="p-north",
    )
    it = response.body_iterator
    await _anext(it)  # retry
    await _anext(it)  # stream_started
    await _anext(it)  # seat_rejoined, from opening this very connection

    for player_id in ("p-east", "p-south", "p-west"):
        container.sse.subscribe(game_id, player_id)
    container.admin.start_game(game_id)

    configured = await _anext(it)
    assert _frame_type(configured) == "game_configured"
    await it.aclose()


async def test_a_private_event_is_not_sent_to_the_wrong_seat(container):
    """NFR-6: a hand dealt to one seat must never reach another's stream."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    for player_id in ("p-north", "p-east", "p-south", "p-west"):
        container.sse.subscribe(game_id, player_id)

    response = await stream_router.player_stream(
        game_id, _request(), container=container, player_id="p-east",
    )
    it = response.body_iterator
    await _anext(it)  # retry
    await _anext(it)  # stream_started

    container.admin.start_game(game_id)
    for position, player_id in enumerate(["p-north", "p-east", "p-south", "p-west"]):
        container.actions.draw_for_deal(game_id, player_id, position)
    while container.state.load(game_id).current_round is None:
        taken = container.admin.positions_taken(game_id)
        free = (i for i in range(container.admin.spread_size(game_id)) if i not in taken)
        for player_id in ["p-north", "p-east", "p-south", "p-west"]:
            container.actions.draw_for_deal(game_id, player_id, next(free))

    seen_types = []
    try:
        while True:
            frame = await _anext(it, timeout=0.2)
            seen_types.append(_frame_type(frame))
            if _frame_type(frame) == "cards_dealt":
                payload = _payload(frame)
                # East's own hand is fine; nobody else's cards ever appear here.
                assert len(payload["cards"]) == 12
    except asyncio.TimeoutError:
        pass
    finally:
        await it.aclose()

    # East's stream must see exactly one cards_dealt (its own), not four.
    assert seen_types.count("cards_dealt") == 1


async def test_a_mid_game_join_is_rebuilt_from_the_replay_buffer(container):
    """RT-5a, FR-10c: a tab opened after the deal is caught up, not left blank."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    for player_id in ("p-north", "p-east", "p-south", "p-west"):
        container.sse.subscribe(game_id, player_id)
    container.admin.start_game(game_id)
    for position, player_id in enumerate(["p-north", "p-east", "p-south", "p-west"]):
        container.actions.draw_for_deal(game_id, player_id, position)
    while container.state.load(game_id).current_round is None:
        taken = container.admin.positions_taken(game_id)
        free = (i for i in range(container.admin.spread_size(game_id)) if i not in taken)
        for player_id in ["p-north", "p-east", "p-south", "p-west"]:
            container.actions.draw_for_deal(game_id, player_id, next(free))

    response = await stream_router.player_stream(
        game_id, _request(), container=container, player_id="p-north",
    )
    it = response.body_iterator
    await _anext(it)  # retry
    started = await _anext(it)
    # Nothing is missing, so this tab is not working from a partial picture.
    assert _payload(started)["partial"] is False
    assert _payload(started)["resume"] == "fresh"

    replayed = await _drain(it)
    # The table it needs to draw, and the hand it needs to play, both arrive.
    assert "game_configured" in replayed
    assert replayed.count("cards_dealt") == 1


async def test_admin_stream_never_receives_a_private_event(container):
    """§6.3: the admin's queues are wired to broadcast only, structurally."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    for player_id in ("p-north", "p-east", "p-south", "p-west"):
        container.sse.subscribe(game_id, player_id)

    response = await admin_router.admin_stream(game_id, container=container)
    it = response.body_iterator
    await _anext(it)  # retry
    await _anext(it)  # stream_started

    container.admin.start_game(game_id)
    for position, player_id in enumerate(["p-north", "p-east", "p-south", "p-west"]):
        container.actions.draw_for_deal(game_id, player_id, position)
    while container.state.load(game_id).current_round is None:
        taken = container.admin.positions_taken(game_id)
        free = (i for i in range(container.admin.spread_size(game_id)) if i not in taken)
        for player_id in ["p-north", "p-east", "p-south", "p-west"]:
            container.actions.draw_for_deal(game_id, player_id, next(free))

    seen_types = []
    try:
        while True:
            frame = await _anext(it, timeout=0.2)
            seen_types.append(_frame_type(frame))
    except asyncio.TimeoutError:
        pass
    finally:
        await it.aclose()

    assert "cards_dealt" not in seen_types
    assert "game_configured" in seen_types


async def _play_to_the_deal(container, game_id: str) -> None:
    """Take a seated game as far as a dealt round, so there is history to miss."""
    container.admin.start_game(game_id)
    for position, player_id in enumerate(["p-north", "p-east", "p-south", "p-west"]):
        container.actions.draw_for_deal(game_id, player_id, position)
    while container.state.load(game_id).current_round is None:
        taken = container.admin.positions_taken(game_id)
        free = (i for i in range(container.admin.spread_size(game_id)) if i not in taken)
        for player_id in ["p-north", "p-east", "p-south", "p-west"]:
            container.actions.draw_for_deal(game_id, player_id, next(free))


async def test_a_dropped_seat_resumes_from_where_it_left_off(container):
    """RT-5a: the frames missed while the connection was down are replayed.

    This is the bug that read as a dead Play button: the seat's stream
    dropped, nothing reconnected it, and the table sat frozen with controls
    that could not work.
    """
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    for player_id in ("p-east", "p-south", "p-west"):
        container.sse.subscribe(game_id, player_id)

    first = await stream_router.player_stream(
        game_id, _request(), container=container, player_id="p-north",
    )
    it = first.body_iterator
    await _anext(it)  # retry
    await _anext(it)  # stream_started
    # seat_rejoined, from opening this very connection: the last thing this
    # browser would have stamped as its Last-Event-ID.
    last_seen = _seq(await _anext(it))
    await it.aclose()  # the connection drops

    # Everything from here on happens while North is not listening.
    await _play_to_the_deal(container, game_id)

    second = await stream_router.player_stream(
        game_id, _request(str(last_seen)), container=container, player_id="p-north",
    )
    it = second.body_iterator
    await _anext(it)  # retry
    started = await _anext(it)
    assert _payload(started)["resume"] == "resumed"

    replayed = await _drain(it)
    assert "game_configured" in replayed
    # North's own hand comes back too — it cannot be re-derived any other way.
    assert replayed.count("cards_dealt") == 1


async def test_a_resume_beyond_the_buffer_is_declared_incomplete(container):
    """A seat that cannot be caught up is told so, not handed a history with a hole."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    container.sse = SseNotification(history_maxlen=1)

    response = await stream_router.player_stream(
        game_id, _request("1"), container=container, player_id="p-north",
    )
    it = response.body_iterator
    await _anext(it)  # retry
    started = await _anext(it)
    assert _payload(started)["resume"] == "incomplete"
    await it.aclose()


async def test_the_opening_frame_carries_no_id_line(container):
    """Its ``id:`` would wind the browser's resume marker back to the deal."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)

    response = await stream_router.player_stream(
        game_id, _request(), container=container, player_id="p-north",
    )
    it = response.body_iterator
    await _anext(it)  # retry
    started = await _anext(it)
    assert _frame_type(started) == "stream_started"
    assert "id:" not in started
    await it.aclose()
