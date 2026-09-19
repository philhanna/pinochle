# tests.web.test_cards_router
import pytest


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
