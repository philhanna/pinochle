# pinochle.web.routers.admin
from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from pinochle.domain.errors import SetupError
from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID, Team
from pinochle.web.container import Container
from pinochle.web.dependencies import get_container, require_admin
from pinochle.web.event_encoder import encode_frame
from pinochle.web.schemas import (
    AbandonRequest,
    CreateGameRequest,
    CreateGameResponse,
    SeatResponse,
)
from pinochle.web.sse_stream import RETRY_LINE, STREAM_HEADERS, sse_frames
from pinochle.web.transport_events import GameAbandoned
from pinochle.web.turn_header import build_turn_header

router = APIRouter(dependencies=[Depends(require_admin)])


@router.post("/api/admin/games", status_code=201)
async def create_game(
    body: CreateGameRequest, container: Container = Depends(get_container),
) -> CreateGameResponse:
    """Create a game and seat all four players in one call (FR-6, FR-7).

    Returns a join link for each human seat (FR-10); it is shown exactly
    once, since there is no way to retrieve a minted token afterwards.
    """
    game_id = container.admin.create_game()
    container.admin.assign_teams(
        game_id, Team(NS_TEAM_ID, body.teams.ns), Team(EW_TEAM_ID, body.teams.ew),
    )

    seats = []
    for seat in body.seats:
        position = Position[seat.seat]
        player_type = PlayerType[seat.type.upper()]
        player_id = f"p-{seat.seat.lower()}"
        container.admin.add_player(
            game_id, Player(player_id, seat.name, player_type, position),
        )

        join_url = None
        if player_type == PlayerType.HUMAN:
            token = container.tokens.mint(game_id, player_id)
            join_url = f"{container.settings.public_base_url}/join/{game_id}?t={token}"

        seats.append(SeatResponse(
            seat=seat.seat, name=seat.name, type=seat.type,
            player_id=player_id, join_url=join_url,
        ))

    return CreateGameResponse(game_id=game_id, seats=seats)


@router.get("/api/admin/games/{game_id}")
async def get_game_status(game_id: str, container: Container = Depends(get_container)) -> dict:
    """Return setup status: the four seats and which human seats have joined."""
    game = container.state.load(game_id)  # UnknownGameError -> 404 if missing
    connected = container.sse.seats_connected(game_id)
    return {
        "game_id": game_id,
        "seats": [
            {
                "seat": player.position.name,
                "player_id": player.id,
                "name": player.name,
                "type": player.type.name.lower(),
                "joined": player.type == PlayerType.COMPUTER or player.id in connected,
            }
            for player in sorted(game.players.values(), key=lambda p: p.position.value)
        ],
    }


@router.post("/api/admin/games/{game_id}/start", status_code=204)
async def start_game(game_id: str, container: Container = Depends(get_container)) -> Response:
    """Validate seating and begin dealer selection (FR-9).

    FR-10b: every human seat must have at least one open stream before play
    can start, so a stale console can't start a game half the table would
    miss.
    """
    game = container.state.load(game_id)
    connected = container.sse.seats_connected(game_id)
    for player in game.players.values():
        if player.type == PlayerType.HUMAN and player.id not in connected:
            raise SetupError(f"{player.position.name} has not joined yet.")

    container.admin.start_game(game_id)
    return Response(status_code=204)


@router.post("/api/admin/games/{game_id}/abandon", status_code=204)
async def abandon_game(
    game_id: str, body: AbandonRequest, container: Container = Depends(get_container),
) -> Response:
    """End a game that cannot be completed (RT-12).

    Broadcasts ``game_abandoned`` and revokes every token issued for the
    game, so a player who still has a join link can no longer use it.
    """
    container.admin.abandon_game(game_id)
    container.notifier.broadcast(game_id, GameAbandoned(game_id=game_id, reason=body.reason))
    container.tokens.revoke_game(game_id)
    return Response(status_code=204)


@router.get("/api/admin/games/{game_id}/stream")
async def admin_stream(game_id: str, container: Container = Depends(get_container)):
    """Open the administrator's SSE stream: public events plus seat notices.

    Subscribed only to broadcasts (§6.3), so it is structurally impossible
    for this stream to ever carry a hand.
    """
    game = container.state.load(game_id)  # UnknownGameError -> 404 if missing
    queue = container.sse.subscribe_admin(game_id)

    async def generate():
        yield RETRY_LINE
        yield encode_frame("stream_started", seq=0, turn=build_turn_header(game), payload={})
        try:
            async for frame in sse_frames(queue, game, container.settings.sse_keepalive_seconds):
                yield frame
        finally:
            container.sse.unsubscribe_admin(game_id, queue)

    return StreamingResponse(generate(), media_type="text/event-stream", headers=STREAM_HEADERS)
