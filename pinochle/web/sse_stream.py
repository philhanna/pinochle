# pinochle.web.sse_stream
import asyncio
from typing import AsyncIterator

from pinochle.domain.game import Game
from pinochle.web.event_encoder import encode_event
from pinochle.web.turn_header import build_turn_header

# Sets EventSource's reconnection delay to a day, since a reconnect could
# not rebuild anything the server does not keep (RT-5, §6.9).
RETRY_LINE = "retry: 86400000\n\n"

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
    closed (the client disconnected), at which point the caller's own
    ``finally`` block does the unsubscribing.
    """
    while True:
        try:
            seq, event = await asyncio.wait_for(queue.get(), timeout=keepalive_seconds)
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"
            continue
        yield encode_event(event, seq, build_turn_header(game))
