# pinochle.web.security
import secrets

from fastapi import Request


def extract_seat_token(request: Request) -> str | None:
    """Return the seat token carried by ``request``, or ``None``.

    Command endpoints carry it in the ``X-Seat-Token`` header (FR-10a); the
    SSE endpoint carries it in the ``?t=`` query parameter instead, because
    ``EventSource`` cannot set request headers (§6.2).
    """
    header = request.headers.get("X-Seat-Token")
    if header:
        return header
    return request.query_params.get("t")


def extract_admin_token(request: Request) -> str | None:
    """Return the admin token carried by ``request``, or ``None``.

    Administrative commands carry it in the ``X-Admin-Token`` header (§5.1).
    The administrator's SSE endpoint accepts it as the ``?t=`` query
    parameter as well, for the same reason the seat token travels that way:
    ``EventSource`` cannot set request headers.  Only that one read-only
    endpoint accepts it — a command that changes a game still requires the
    header, so a token cannot reach a mutating route through a URL someone
    was sent.
    """
    header = request.headers.get("X-Admin-Token")
    if header:
        return header
    return request.query_params.get("t")


def admin_token_matches(provided: str | None, expected: str) -> bool:
    """Return whether ``provided`` matches ``expected``, in constant time."""
    if provided is None:
        return False
    return secrets.compare_digest(provided, expected)
