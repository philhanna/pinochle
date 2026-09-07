# tests.web.test_admin_router
from pinochle.domain.game import GamePhase
from tests.web.conftest import FOUR_HUMAN_SEATS, admin_headers, seat_players


async def test_create_game_requires_the_admin_token(client):
    """A missing/wrong admin token is rejected before any game logic runs."""
    response = await client.post("/api/admin/games", json=FOUR_HUMAN_SEATS)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_admin"


async def test_create_game_seats_all_four_and_mints_join_links(client):
    """FR-6, FR-7, FR-10: one call creates the game and issues human tokens."""
    response = await client.post(
        "/api/admin/games", json=FOUR_HUMAN_SEATS, headers=admin_headers(),
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["seats"]) == 4
    for seat in body["seats"]:
        assert seat["type"] == "human"
        assert seat["join_url"].startswith("http://localhost:8000/join/")
        assert "?t=" in seat["join_url"]


async def test_create_game_gives_computer_seats_no_join_link(client):
    """A computer seat needs no credential, since nobody has to open it."""
    body = dict(FOUR_HUMAN_SEATS)
    body["seats"] = [dict(FOUR_HUMAN_SEATS["seats"][0], type="computer")] + FOUR_HUMAN_SEATS["seats"][1:]
    response = await client.post("/api/admin/games", json=body, headers=admin_headers())
    seats = response.json()["seats"]
    assert seats[0]["type"] == "computer"
    assert seats[0]["join_url"] is None


async def test_start_rejects_until_every_human_seat_has_joined(container, client):
    """FR-10b: a stale console can't start a game half the table would miss."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)

    response = await client.post(f"/api/admin/games/{game_id}/start", headers=admin_headers())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "setup_incomplete"
    assert container.state.load(game_id).phase == GamePhase.SETUP


async def test_start_succeeds_once_every_human_seat_is_connected(container, client):
    """Subscribing each seat's stream first, start then proceeds (FR-9)."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    for player_id in ("p-north", "p-east", "p-south", "p-west"):
        container.sse.subscribe(game_id, player_id)

    response = await client.post(f"/api/admin/games/{game_id}/start", headers=admin_headers())
    assert response.status_code == 204
    assert container.state.load(game_id).phase == GamePhase.DEALER_SELECTION


async def test_get_game_status_reports_joined_seats(container, client):
    """The admin console's join board reads connection state per seat."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    container.sse.subscribe(game_id, "p-north")

    response = await client.get(f"/api/admin/games/{game_id}", headers=admin_headers())
    seats = {s["seat"]: s["joined"] for s in response.json()["seats"]}
    assert seats == {"NORTH": True, "EAST": False, "SOUTH": False, "WEST": False}


async def test_unknown_game_status_is_404(client):
    """Looking up a game that was never created should be a clean 404."""
    response = await client.get("/api/admin/games/does-not-exist", headers=admin_headers())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_game"


async def test_abandon_finishes_the_game_and_revokes_tokens(container, client):
    """RT-12: an abandoned game's join links must stop working."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    token = container.tokens.mint(game_id, "p-north")

    response = await client.post(
        f"/api/admin/games/{game_id}/abandon",
        json={"reason": "a player disconnected"},
        headers=admin_headers(),
    )
    assert response.status_code == 204
    assert container.state.load(game_id).phase == GamePhase.FINISHED
    assert container.tokens.resolve(game_id, token) is None
