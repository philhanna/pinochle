# tests.web.test_cards_router
import httpx
import pytest

from pinochle.adapters.fake_scheduler import FakeScheduler
from pinochle.web.container import Container, Settings, build_container
from pinochle.web.main import create_app
from tests.web.conftest import ADMIN_TOKEN


async def test_serves_a_card_face_by_its_wire_code(client):
    """UI-16: the client asks for artwork with the same code the stream uses."""
    response = await client.get("/cards/faces/TS")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in response.content


async def test_accepts_a_lowercase_code(client):
    """A code is case-insensitive, so a hand-typed URL works too."""
    assert (await client.get("/cards/faces/ah")).status_code == 200


async def test_serves_a_card_face_as_png(client):
    """UI-16 requires at least one format per card; both are available."""
    response = await client.get("/cards/faces/KD", params={"fmt": "png"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


async def test_serves_the_default_card_back(client):
    """UI-5: the other three hands are drawn as backs."""
    response = await client.get("/cards/backs/blue")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"


async def test_artwork_is_cacheable_forever(client):
    """A fanned hand plus three fans of backs is ~50 requests per render."""
    response = await client.get("/cards/faces/TS")
    assert "immutable" in response.headers["cache-control"]


@pytest.mark.parametrize("code", ["2S", "XX", "T", "TSS", "%20"])
async def test_rejects_a_code_that_is_not_a_pinochle_card(client, code):
    """A rank outside the pinochle deck is as invalid as a malformed code."""
    response = await client.get(f"/cards/faces/{code}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


async def test_rejects_an_unsupported_format(client):
    """Only the two bundled formats are served."""
    response = await client.get("/cards/faces/TS", params={"fmt": "webp"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("name", ["blue.svg", "Blue", "blue-2", "blue%20"])
async def test_rejects_a_back_name_that_is_not_a_plain_asset_name(client, name):
    """The back name is client-supplied, so only a bare asset name is allowed."""
    response = await client.get(f"/cards/backs/{name}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("name", ["..%2f..%2fapp", "..", "%2e%2e%2fpyproject.toml"])
async def test_a_traversing_back_name_never_reaches_the_asset_directory(client, name):
    """Refused somewhere between URL normalisation and the name whitelist.

    Which layer catches it is not the point; that nothing outside
    ``card_images/`` is ever served is.
    """
    response = await client.get(f"/cards/backs/{name}")
    assert response.status_code in (404, 422)
    assert b"[project]" not in response.content


async def test_missing_artwork_is_a_404_not_a_500(client):
    """A well-formed name with nothing on disk is a plain not-found."""
    response = await client.get("/cards/backs/no_such_back")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_serves_the_back_this_deployment_was_configured_with(configured_client):
    """PINOCHLE_CARD_BACK names the file; the client only asks for the back."""
    response = await configured_client.get("/cards/back")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    named = await configured_client.get("/cards/backs/castle")
    assert response.content == named.content


async def test_the_configured_back_is_available_as_png(configured_client):
    """Both bundled formats, as for every other piece of artwork."""
    response = await configured_client.get("/cards/back", params={"fmt": "png"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


async def test_the_configured_back_is_rechecked_rather_than_kept_for_a_year(configured_client):
    """Its URL is fixed but its content follows the configuration."""
    response = await configured_client.get("/cards/back")
    assert response.headers["cache-control"] == "no-cache"


@pytest.fixture
async def configured_client(container_with_card_back):
    """A client for a server configured with the castle back."""
    app = create_app(container_with_card_back)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def container_with_card_back() -> Container:
    """A container whose settings name a back other than the default."""
    settings = Settings(admin_token=ADMIN_TOKEN, card_back="castle")
    return build_container(settings, scheduler=FakeScheduler())
