# tests.web.conftest
import httpx
import pytest

from pinochle.adapters.fake_scheduler import FakeScheduler
from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID, Team
from pinochle.web.container import Container, Settings, build_container
from pinochle.web.main import create_app

ADMIN_TOKEN = "test-admin-token"

FOUR_HUMAN_SEATS = {
    "teams": {"ns": "Us", "ew": "Them"},
    "seats": [
        {"seat": "NORTH", "name": "Phil", "type": "human"},
        {"seat": "EAST", "name": "Ada", "type": "human"},
        {"seat": "SOUTH", "name": "Grace", "type": "human"},
        {"seat": "WEST", "name": "Turing", "type": "human"},
    ],
}


@pytest.fixture
def container() -> Container:
    """A container with a FakeScheduler and no artificial computer delay.

    Tests advance the fake clock explicitly rather than waiting in real time
    (ARC-10).
    """
    settings = Settings(admin_token=ADMIN_TOKEN, computer_delay_seconds=0, trick_clear_seconds=0)
    return build_container(settings, scheduler=FakeScheduler())


@pytest.fixture
async def client(container: Container):
    """An httpx client wired to the app over its ASGI transport, no sockets."""
    app = create_app(container)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def admin_headers() -> dict:
    """The header a request needs to pass ``require_admin``."""
    return {"X-Admin-Token": ADMIN_TOKEN}


def seat_players(container: Container, game_id: str) -> None:
    """Seat the four human players used by ``FOUR_HUMAN_SEATS`` directly.

    A lower-level shortcut than going through the HTTP layer, for tests that
    only care about what happens after setup.
    """
    container.admin.assign_teams(game_id, Team(NS_TEAM_ID, "Us"), Team(EW_TEAM_ID, "Them"))
    for player_id, name, position in [
        ("p-north", "Phil", Position.NORTH),
        ("p-east", "Ada", Position.EAST),
        ("p-south", "Grace", Position.SOUTH),
        ("p-west", "Turing", Position.WEST),
    ]:
        container.admin.add_player(game_id, Player(player_id, name, PlayerType.HUMAN, position))
