# pinochle.web.routers.stream
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from pinochle.web.container import Container
from pinochle.web.dependencies import get_container, require_seat
from pinochle.web.event_encoder import encode_event, encode_frame
from pinochle.web.sse_stream import RETRY_LINE, STREAM_HEADERS, sse_frames
from pinochle.web.transport_events import SeatLost, SeatRejoined
from pinochle.web.turn_header import build_turn_header

router = APIRouter()

_log = logging.getLogger("pinochle.stream")


@router.get("/api/games/{game_id}/stream")
async def player_stream(
    game_id: str,
    request: Request,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
):
    """Open — or reopen — the player's SSE connection (§6.2, RT-5a).

    A browser that reconnects sends back the last ``id:`` it saw, so the
    frames this seat missed while it was away are replayed before the live
    relay starts and the client carries on folding where it left off.  Only
    then does it relay every new event addressed to this seat, until the
    connection drops.
    """
    game = container.state.load(game_id)  # UnknownGameError -> 404 if missing
    player = game.players[player_id]

    after_seq = _resume_point(request)
    was_connected = player_id in container.sse.seats_connected(game_id)
    # Nothing may be awaited between these two calls.  The queue starts
    # collecting live events the moment it is registered, so an event
    # dispatched in any gap here would land in both the replay and the queue,
    # and the client's reducer is not idempotent (a replayed ``bid_placed``
    # would append a second bid).  Subscribing first and reading the history
    # second means the two meet exactly, with no overlap and no hole.
    queue = container.sse.subscribe(game_id, player_id)
    missed, whole = container.sse.history_since(game_id, player_id, after_seq)

    resume = _resume_mode(after_seq, whole)
    _log.info(
        "stream.opened game_id=%s player_id=%s resume=%s after_seq=%s replay=%d",
        game_id, player_id, resume, after_seq, len(missed),
    )
    if resume == "incomplete":
        _log.warning(
            "stream.replay_incomplete game_id=%s player_id=%s after_seq=%s "
            "— the replay buffer no longer reaches that far back",
            game_id, player_id, after_seq,
        )

    if not was_connected:
        container.notifier.broadcast(
            game_id, SeatRejoined(game_id=game_id, player_id=player_id),
        )

    async def generate():
        yield RETRY_LINE
        yield encode_frame(
            "stream_started",
            seq=0,
            turn=build_turn_header(game),
            payload={
                "seat": player.position.name,
                "player_id": player_id,
                "you": {"name": player.name, "type": player.type.name.lower()},
                # Partial only if the replay could not reach back far enough:
                # a tab opened mid-game is no longer necessarily behind, since
                # the buffer often holds the whole round it walked in on.
                "partial": game.current_round is not None and not whole,
                "resume": resume,
            },
        )
        # Replayed frames carry the turn header as it is now rather than as it
        # was, because no header is kept with the history.  That is enough:
        # the client folds the whole replay before it draws, so it is the last
        # frame's header that it ends up rendering, and that one is current.
        for seq, event in missed:
            yield encode_event(event, seq, build_turn_header(game))
        try:
            async for frame in sse_frames(queue, game, container.settings.sse_keepalive_seconds):
                yield frame
        finally:
            container.sse.unsubscribe(game_id, player_id, queue)
            still_seated = player_id in container.sse.seats_connected(game_id)
            _log.info(
                "stream.closed game_id=%s player_id=%s other_connections=%s",
                game_id, player_id, still_seated,
            )
            if not still_seated:
                container.notifier.broadcast(
                    game_id, SeatLost(game_id=game_id, player_id=player_id),
                )

    return StreamingResponse(generate(), media_type="text/event-stream", headers=STREAM_HEADERS)


def _resume_point(request: Request) -> int:
    """Return the sequence number this client last saw, or 0 for a fresh stream.

    ``EventSource`` sends the last ``id:`` it received back in the
    ``Last-Event-ID`` header when it reconnects.  It is client-supplied, so a
    value that isn't a sequence number at all is treated as a fresh stream
    rather than an error — the worst case is a client that replays from the
    beginning, which is what it would have got anyway.
    """
    header = request.headers.get("Last-Event-ID")
    if header is None:
        return 0
    try:
        return max(0, int(header))
    except ValueError:
        _log.warning("stream.bad_last_event_id value=%r", header)
        return 0


def _resume_mode(after_seq: int, whole: bool) -> str:
    """Classify this connection for the client: fresh, resumed, or incomplete.

    ``incomplete`` is the honest answer when a seat asks to resume from
    further back than the replay buffer still holds: the client is told it
    has a hole rather than being handed a partial history it would fold in
    and be quietly wrong about.
    """
    if after_seq == 0:
        return "fresh"
    return "resumed" if whole else "incomplete"
