# pinochle.web.routers.stream
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from pinochle.web.container import Container
from pinochle.web.dependencies import get_container, require_seat
from pinochle.web.event_encoder import encode_frame
from pinochle.web.sse_stream import RETRY_LINE, STREAM_HEADERS, sse_frames
from pinochle.web.transport_events import SeatLost, SeatRejoined
from pinochle.web.turn_header import build_turn_header

router = APIRouter()


@router.get("/api/games/{game_id}/stream")
async def player_stream(
    game_id: str,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
):
    """Open the player's SSE connection (§6.2).

    Suppresses ``EventSource``'s auto-reconnect (RT-5 — there is nothing a
    reconnect could rebuild), then relays every event addressed to this seat
    until the connection drops.
    """
    game = container.state.load(game_id)  # UnknownGameError -> 404 if missing
    player = game.players[player_id]

    was_connected = player_id in container.sse.seats_connected(game_id)
    queue = container.sse.subscribe(game_id, player_id)
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
                "partial": game.current_round is not None,
            },
        )
        try:
            async for frame in sse_frames(queue, game, container.settings.sse_keepalive_seconds):
                yield frame
        finally:
            container.sse.unsubscribe(game_id, player_id, queue)
            if player_id not in container.sse.seats_connected(game_id):
                container.notifier.broadcast(
                    game_id, SeatLost(game_id=game_id, player_id=player_id),
                )

    return StreamingResponse(generate(), media_type="text/event-stream", headers=STREAM_HEADERS)
