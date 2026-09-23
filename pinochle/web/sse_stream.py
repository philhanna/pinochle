# pinochle.web.sse_stream
import asyncio
from typing import AsyncIterator

from pinochle.adapters.sse_notification import STREAM_CLOSED
from pinochle.domain.game import Game
from pinochle.web.event_encoder import encode_event
from pinochle.web.turn_header import build_turn_header

# How long EventSource waits before reconnecting a dropped stream.  Short,
# because a reconnect now recovers the seat rather than showing it a dead
# table: the server replays what the seat missed from its ``Last-Event-ID``
# (RT-5a).  Two seconds is long enough not to hammer a server that is down
# and short enough that a blip is over before a player finishes noticing it.
RETRY_LINE = "retry: 2000\n\n"

STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    # nginx honours this so a reverse proxy does not buffer the stream (§10.5).
    "X-Accel-Buffering": "no",
}


async def sse_frames(
    queue: asyncio.Queue, game: Game, keepalive_seconds: float,
) -> AsyncIterator[str]:
    """Yield encoded frames from ``queue`` forever, with periodic keepalives.

    A comment line every ``keepalive_seconds`` with no traffic keeps an idle
    connection from being reaped (§6.8) — a Pinochle table can sit idle for
    minutes while a human thinks.  Runs until the caller's generator is
    closed (the client disconnected) or the server puts ``STREAM_CLOSED`` on
    the queue (the seat was unlinked), at which point the caller's own
    ``finally`` block does the unsubscribing.
    """
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=keepalive_seconds)
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"
            continue
        if item is STREAM_CLOSED:
            # The server is ending this stream: the administrator has
            # unlinked the seat (RT-12a).  Returning runs the caller's own
            # ``finally``, which unsubscribes and tells the table the seat is
            # gone, exactly as if the client had disconnected.
            return
        seq, event = item
        yield encode_event(event, seq, build_turn_header(game))
