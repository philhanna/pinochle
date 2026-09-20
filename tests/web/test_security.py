# tests.web.test_security
from fastapi import Request

from pinochle.web.security import (
    admin_token_matches,
    extract_admin_token,
    extract_seat_token,
)


def _request(headers: dict | None = None, query_string: bytes = b"") -> Request:
    """Build a minimal ASGI ``Request`` carrying the given headers/query string."""
    raw_headers = [
        (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "headers": raw_headers,
        "query_string": query_string,
        "method": "GET",
        "path": "/",
    }
    return Request(scope)


def test_extract_seat_token_prefers_the_header():
    """Command endpoints carry the token in X-Seat-Token (FR-10a)."""
    request = _request(headers={"X-Seat-Token": "abc"}, query_string=b"t=xyz")
    assert extract_seat_token(request) == "abc"


def test_extract_seat_token_falls_back_to_the_query_string():
    """EventSource cannot set headers, so the stream endpoint uses ?t= (§6.2)."""
    request = _request(query_string=b"t=xyz")
    assert extract_seat_token(request) == "xyz"


def test_extract_seat_token_returns_none_when_absent():
    """No credential at all should resolve to no token, not an empty string."""
    request = _request()
    assert extract_seat_token(request) is None


def test_admin_token_matches_the_configured_value():
    """A correct admin token should be accepted."""
    assert admin_token_matches("secret", "secret") is True


def test_admin_token_rejects_a_wrong_value():
    """An incorrect admin token should be rejected."""
    assert admin_token_matches("wrong", "secret") is False


def test_admin_token_rejects_a_missing_value():
    """A missing admin token (None) should be rejected, not raise."""
    assert admin_token_matches(None, "secret") is False


# ---------------------------------------------------------------------------
# The administrator's token (§5.1, §6.2)
# ---------------------------------------------------------------------------

def test_extract_admin_token_prefers_the_header():
    """Administrative commands carry it in X-Admin-Token."""
    request = _request(headers={"X-Admin-Token": "abc"}, query_string=b"t=xyz")
    assert extract_admin_token(request) == "abc"


def test_extract_admin_token_falls_back_to_the_query_string():
    """The administrator's EventSource stream cannot set a header either."""
    assert extract_admin_token(_request(query_string=b"t=xyz")) == "xyz"


def test_extract_admin_token_returns_none_when_absent():
    """No credential at all is None, not an empty string."""
    assert extract_admin_token(_request()) is None
