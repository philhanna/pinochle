# tests.web.test_errors
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pinochle.domain.errors import (
    IllegalActionError,
    NotYourTurnError,
    SetupError,
    UnknownGameError,
    WrongPhaseError,
)
from pinochle.web.errors import ForbiddenError, register_error_handlers


def _app_that_raises(exc: Exception) -> FastAPI:
    """Build a tiny app whose one route always raises ``exc``, for handler tests."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom():
        raise exc

    return app


async def _assert_maps_to(exc: Exception, status: int, code: str) -> None:
    """Assert that raising ``exc`` from a route produces the §5.5 envelope."""
    app = _app_that_raises(exc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/boom")
    assert response.status_code == status
    body = response.json()
    assert body["error"]["code"] == code
    assert body["error"]["message"]


async def test_unknown_game_error_maps_to_404():
    await _assert_maps_to(UnknownGameError("g1"), 404, "unknown_game")


async def test_not_your_turn_error_maps_to_409():
    await _assert_maps_to(NotYourTurnError("not your turn"), 409, "not_your_turn")


async def test_wrong_phase_error_maps_to_409():
    await _assert_maps_to(WrongPhaseError("wrong phase"), 409, "wrong_phase")


async def test_illegal_action_error_maps_to_409():
    await _assert_maps_to(IllegalActionError("illegal"), 409, "illegal_action")


async def test_setup_error_maps_to_409():
    await _assert_maps_to(SetupError("setup incomplete"), 409, "setup_incomplete")


async def test_forbidden_error_maps_to_403_with_its_own_code():
    await _assert_maps_to(ForbiddenError("forbidden_seat", "bad seat token"), 403, "forbidden_seat")
