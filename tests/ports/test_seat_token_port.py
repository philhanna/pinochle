# tests.ports.test_seat_token_port
"""Contract tests for SeatTokenPort."""
from pinochle.ports.seat_token_port import SeatTokenPort


def run_contract(tokens: SeatTokenPort) -> None:
    """Assert a seat-token adapter can mint, resolve, and revoke tokens."""
    token = tokens.mint("g1", "N")
    assert isinstance(token, str) and len(token) > 0
    assert tokens.resolve("g1", token) == "N"

    assert tokens.resolve("g1", "not-a-real-token") is None
    assert tokens.resolve("other-game", token) is None

    tokens.revoke_game("g1")
    assert tokens.resolve("g1", token) is None
