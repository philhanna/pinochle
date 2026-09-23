# pinochle.web.routers.admin
from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from pinochle.domain.errors import IllegalActionError, SetupError
from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID, Team
from pinochle.web.container import Container
from pinochle.web.dependencies import (
    get_container,
    require_admin,
    require_admin_stream,
)
from pinochle.web.event_encoder import encode_frame
from pinochle.web.schemas import (
    AbandonRequest,
    CreateGameRequest,
    CreateGameResponse,
    SeatDefaultResponse,
    SeatResponse,
    TableDefaultsResponse,
    TeamsRequest,
)
from pinochle.web.sse_stream import RETRY_LINE, STREAM_HEADERS, sse_frames
from pinochle.web.transport_events import GameAbandoned
from pinochle.web.turn_header import build_turn_header

router = APIRouter(dependencies=[Depends(require_admin)])

# The administrator's stream is guarded separately because it is the one
# admin route an ``EventSource`` opens, so it must accept its token from
# the query string.  Keeping it on its own router is what confines that to
# a read-only route: every command above still requires the header.
stream_router = APIRouter(dependencies=[Depends(require_admin_stream)])


@router.get("/api/admin/defaults")
async def get_defaults(
    container: Container = Depends(get_container),
) -> TableDefaultsResponse:
    """Return the table the console's setup form should start out holding (§10.4).

    Behind the admin token like every other console route. The names on it are
    the operator's own household — real people, configured once in ``.env`` —
    and there is no reason for anyone who cannot already run the console to be
    able to read them.
    """
    table = container.settings.table
    return TableDefaultsResponse(
        teams=TeamsRequest(ns=table.ns, ew=table.ew),
        seats=[
            SeatDefaultResponse(seat=seat, name=default.name, type=default.type)
            for seat, default in table.seats.items()
        ],
    )


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


@router.post("/api/admin/games/{game_id}/seats/{player_id}/unlink", status_code=204)
async def unlink_seat(
    game_id: str, player_id: str, container: Container = Depends(get_container),
) -> Response:
    """Cut a player loose from their seat (RT-12a).

    Revokes the seat's credentials and ends the streams held open with them,
    so the link the player was sent stops working and their table stops being
    told what happens.  The seat itself is untouched: it keeps its cards and
    its turn, and play blocks there exactly as it does for a player whose
    connection dropped (RT-12), until a computer is seated in it or the game
    is abandoned.

    The order matters.  The credential goes first, so that a tab still open
    on the player's screen cannot slip an action in between the two.
    """
    _human_seat(container, game_id, player_id)
    container.tokens.revoke_seat(game_id, player_id)
    container.sse.close_seat(game_id, player_id)
    return Response(status_code=204)


@router.post("/api/admin/games/{game_id}/seats/{player_id}/computer", status_code=204)
async def seat_computer(
    game_id: str, player_id: str, container: Container = Depends(get_container),
) -> Response:
    """Seat a computer where a player has gone, and let play resume (RT-12a).

    The whole point of RT-12a: a table that has stopped because one of four
    people closed their laptop goes on for the three who are still at it,
    from the point it stopped rather than from a fresh deal.  The seat keeps
    its id, its place and its hand, so a round in progress carries on; if the
    seat was the one on the clock, its move follows a moment later like any
    other computer's.

    Unlinks first, whether or not the player is still connected: an old tab
    left open would otherwise still hold a working credential for a seat the
    computer is now playing.
    """
    _human_seat(container, game_id, player_id)
    container.tokens.revoke_seat(game_id, player_id)
    container.sse.close_seat(game_id, player_id)
    container.admin.seat_computer(game_id, player_id)
    return Response(status_code=204)


def _human_seat(container: Container, game_id: str, player_id: str) -> None:
    """Refuse a seat that is not a human player's to unlink (RT-12a).

    Checked before anything is revoked, so that a console acting on a stale
    view of the table changes nothing at all.  An unknown id is not a lookup
    failure of the game — the game is there — so it is refused as the illegal
    action it is, naming what was asked for.
    """
    game = container.state.load(game_id)  # UnknownGameError -> 404 if missing
    player = game.players.get(player_id)
    if player is None:
        raise IllegalActionError(f"Unknown player: {player_id}")
    if player.type != PlayerType.HUMAN:
        raise IllegalActionError(
            f"{player.position.name} is played by the computer already.")


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


@stream_router.get("/api/admin/games/{game_id}/stream")
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
