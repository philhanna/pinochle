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


def admin_token_matches(provided: str | None, expected: str) -> bool:
    """Return whether ``provided`` matches ``expected``, in constant time."""
    if provided is None:
        return False
    return secrets.compare_digest(provided, expected)
