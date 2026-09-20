# pinochle.web.dependencies
from fastapi import Request

from pinochle.web.container import Container
from pinochle.web.errors import ForbiddenError
from pinochle.web.security import (
    admin_token_matches,
    extract_admin_token,
    extract_seat_token,
)


def get_container(request: Request) -> Container:
    """Return the object graph the running app was built with."""
    return request.app.state.container


def require_admin(request: Request) -> None:
    """Raise ``ForbiddenError`` unless ``X-Admin-Token`` matches (§5.1)."""
    container = get_container(request)
    provided = request.headers.get("X-Admin-Token")
    if not admin_token_matches(provided, container.settings.admin_token):
        raise ForbiddenError("forbidden_admin", "Bad admin token.")


def require_admin_stream(request: Request) -> None:
    """Raise ``ForbiddenError`` unless the admin token checks out.

    Accepts the token from the header or from ``?t=``, because the only
    route using this guard is the administrator's ``EventSource`` stream.
    """
    container = get_container(request)
    if not admin_token_matches(extract_admin_token(request), container.settings.admin_token):
        raise ForbiddenError("forbidden_admin", "Bad admin token.")


def require_seat(game_id: str, request: Request) -> str:
    """Resolve the request's seat token to a player id, or raise ``ForbiddenError``.

    ``game_id`` is taken from the route's path parameter of the same name.
    """
    container = get_container(request)
    token = extract_seat_token(request)
    player_id = container.tokens.resolve(game_id, token) if token else None
    if player_id is None:
        raise ForbiddenError(
            "forbidden_seat", "Missing, unknown, or wrong-game seat token.",
        )
    return player_id
