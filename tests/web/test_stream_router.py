# tests.web.test_stream_router
import asyncio
import json

from pinochle.web.routers import admin as admin_router
from pinochle.web.routers import stream as stream_router
from tests.web.conftest import seat_players


async def _anext(iterator, timeout: float = 1.0):
    """Pull the next frame from a stream generator, failing fast if it hangs."""
    return await asyncio.wait_for(iterator.__anext__(), timeout=timeout)


def _frame_type(raw: str) -> str:
    """Return the ``event:`` name from a raw SSE frame."""
    for line in raw.splitlines():
        if line.startswith("event: "):
            return line[len("event: "):]
    raise AssertionError(f"no event: line in frame: {raw!r}")


def _payload(raw: str) -> dict:
    """Return the JSON payload embedded in a raw SSE frame's data: line."""
    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: "):])["payload"]
    raise AssertionError(f"no data: line in frame: {raw!r}")


async def test_player_stream_opens_with_retry_then_stream_started(container):
    """§6.2, §6.9: the connection suppresses auto-reconnect, then identifies the seat."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)

    response = await stream_router.player_stream(game_id, container=container, player_id="p-north")
    it = response.body_iterator
    assert await _anext(it) == "retry: 86400000\n\n"
    started = await _anext(it)
    assert _frame_type(started) == "stream_started"
    assert _payload(started)["seat"] == "NORTH"
    assert _payload(started)["player_id"] == "p-north"
    await it.aclose()


async def test_broadcasts_reach_the_subscribed_seat(container):
    """A public event published after the stream opens should be relayed."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)

    response = await stream_router.player_stream(game_id, container=container, player_id="p-north")
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

    response = await stream_router.player_stream(game_id, container=container, player_id="p-east")
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


async def test_stream_started_marks_a_mid_game_join_as_partial(container):
    """§6.9: a tab opened after the deal is authorised but can't show a table."""
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

    response = await stream_router.player_stream(game_id, container=container, player_id="p-north")
    it = response.body_iterator
    await _anext(it)  # retry
    started = await _anext(it)
    assert _payload(started)["partial"] is True
    await it.aclose()


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
