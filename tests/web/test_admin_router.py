# tests.web.test_admin_router
from pinochle.domain.game import GamePhase
from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID, Team
from pinochle.web.container import (
    DEFAULT_SEATS,
    DEFAULT_TEAM_EW,
    DEFAULT_TEAM_NS,
    SeatDefault,
    TableDefaults,
)
from tests.web.conftest import (
    ADMIN_TOKEN,
    FOUR_HUMAN_SEATS,
    admin_headers,
    seat_players,
)


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


# ---------------------------------------------------------------------------
# Unlinking a player, and seating a computer in their place (RT-12a)
# ---------------------------------------------------------------------------

async def test_unlink_revokes_the_seats_links_and_closes_its_streams(container, client):
    """RT-12a: the player is cut loose, but the seat stays exactly as it was."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    token = container.tokens.mint(game_id, "p-north")
    container.sse.subscribe(game_id, "p-north")

    response = await client.post(
        f"/api/admin/games/{game_id}/seats/p-north/unlink", headers=admin_headers(),
    )

    assert response.status_code == 204
    assert container.tokens.resolve(game_id, token) is None
    assert container.sse.seats_connected(game_id) == set()
    # The seat itself is untouched: play still blocks there (RT-12) until a
    # computer is seated in it.
    assert container.state.load(game_id).players["p-north"].type.name == "HUMAN"


async def test_unlink_leaves_the_other_seats_alone(container, client):
    """One player leaving is not three, however the console phrases it."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    kept = container.tokens.mint(game_id, "p-east")
    container.sse.subscribe(game_id, "p-east")

    await client.post(
        f"/api/admin/games/{game_id}/seats/p-north/unlink", headers=admin_headers(),
    )

    assert container.tokens.resolve(game_id, kept) == "p-east"
    assert container.sse.seats_connected(game_id) == {"p-east"}


async def test_seating_a_computer_replaces_the_seat_and_unlinks_its_player(container, client):
    """RT-12a: the computer takes the seat over, credential and all."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    token = container.tokens.mint(game_id, "p-west")
    container.sse.subscribe(game_id, "p-west")

    response = await client.post(
        f"/api/admin/games/{game_id}/seats/p-west/computer", headers=admin_headers(),
    )

    assert response.status_code == 204
    seated = container.state.load(game_id).players["p-west"]
    assert seated.type == PlayerType.COMPUTER
    assert (seated.id, seated.name, seated.position.name) == ("p-west", "Turing", "WEST")
    assert container.tokens.resolve(game_id, token) is None


async def test_a_replaced_seat_reads_as_joined_on_the_console(container, client):
    """The console's board stops waiting on a seat nobody is coming back to."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    await client.post(
        f"/api/admin/games/{game_id}/seats/p-west/computer", headers=admin_headers(),
    )

    response = await client.get(f"/api/admin/games/{game_id}", headers=admin_headers())
    west = next(s for s in response.json()["seats"] if s["seat"] == "WEST")
    assert (west["type"], west["joined"]) == ("computer", True)


async def test_a_game_can_start_once_an_absent_seat_is_given_to_the_computer(container, client):
    """FR-10b's block is lifted by filling the seat, not by ignoring it."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    for player_id in ("p-north", "p-east", "p-south"):
        container.sse.subscribe(game_id, player_id)

    refused = await client.post(f"/api/admin/games/{game_id}/start", headers=admin_headers())
    assert refused.status_code == 409

    await client.post(
        f"/api/admin/games/{game_id}/seats/p-west/computer", headers=admin_headers(),
    )
    started = await client.post(f"/api/admin/games/{game_id}/start", headers=admin_headers())
    assert started.status_code == 204
    assert container.state.load(game_id).phase == GamePhase.DEALER_SELECTION


async def test_seating_a_computer_twice_is_refused(container, client):
    """The second call is a stale console, and is told which seat it means."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    await client.post(
        f"/api/admin/games/{game_id}/seats/p-west/computer", headers=admin_headers(),
    )

    response = await client.post(
        f"/api/admin/games/{game_id}/seats/p-west/computer", headers=admin_headers(),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "illegal_action"


async def test_unlinking_a_computer_seat_is_refused_before_anything_is_revoked(
    container, client,
):
    """Nothing to unlink, and nothing changed by asking."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    container.admin.seat_computer(game_id, "p-west")
    kept = container.tokens.mint(game_id, "p-north")

    response = await client.post(
        f"/api/admin/games/{game_id}/seats/p-west/unlink", headers=admin_headers(),
    )
    assert response.status_code == 409
    assert container.tokens.resolve(game_id, kept) == "p-north"


async def test_seating_a_computer_in_an_unknown_seat_is_refused(container, client):
    """A player id that seats nobody is an illegal action, not a missing game."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)

    response = await client.post(
        f"/api/admin/games/{game_id}/seats/p-nobody/computer", headers=admin_headers(),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "illegal_action"


async def test_seating_a_computer_in_an_unknown_game_is_a_404(client):
    """A game this process never had is still reported as a missing game."""
    response = await client.post(
        "/api/admin/games/no-such-game/seats/p-west/computer", headers=admin_headers(),
    )
    assert response.status_code == 404


async def test_unlink_requires_the_admin_token(container, client):
    """Neither route is anything a player may reach (§5.1)."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    token = container.tokens.mint(game_id, "p-north")

    response = await client.post(f"/api/admin/games/{game_id}/seats/p-north/unlink")

    assert response.status_code == 403
    assert container.tokens.resolve(game_id, token) == "p-north"


async def test_seating_a_computer_requires_the_admin_token(container, client):
    """The same guard, on the route that actually changes the table."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)

    response = await client.post(f"/api/admin/games/{game_id}/seats/p-north/computer")

    assert response.status_code == 403
    assert container.state.load(game_id).players["p-north"].type == PlayerType.HUMAN


async def test_the_table_plays_on_once_the_absent_seat_is_given_to_the_computer(
    container, client,
):
    """RT-12a end to end: the console's button reaches the computer driver."""
    game_id = container.admin.create_game()
    container.admin.assign_teams(game_id, Team(NS_TEAM_ID, "Us"), Team(EW_TEAM_ID, "Them"))
    for player_id, name, position, kind in [
        ("p-north", "North", Position.NORTH, PlayerType.COMPUTER),
        ("p-east", "East", Position.EAST, PlayerType.COMPUTER),
        ("p-south", "Grace", Position.SOUTH, PlayerType.HUMAN),
        ("p-west", "West", Position.WEST, PlayerType.COMPUTER),
    ]:
        container.admin.add_player(game_id, Player(player_id, name, kind, position))
    container.sse.subscribe(game_id, "p-south")

    await client.post(f"/api/admin/games/{game_id}/start", headers=admin_headers())
    for _ in range(50):
        container.scheduler.advance(0)
    # South has not drawn, so dealer selection cannot settle: the table has
    # stopped where its absent player left it (RT-12).
    assert container.state.load(game_id).phase == GamePhase.DEALER_SELECTION

    response = await client.post(
        f"/api/admin/games/{game_id}/seats/p-south/computer", headers=admin_headers(),
    )
    assert response.status_code == 204

    for _ in range(200):
        if container.state.load(game_id).phase != GamePhase.DEALER_SELECTION:
            break
        container.scheduler.advance(0)
    else:
        raise AssertionError("the table never moved on after the seat was filled")


# ---------------------------------------------------------------------------
# The administrator's stream token (§5.1, §6.2)
# ---------------------------------------------------------------------------

async def test_the_admin_stream_rejects_a_wrong_query_token(client):
    """A bad token is a 403 whichever way it arrives."""
    response = await client.post(
        "/api/admin/games", json=FOUR_HUMAN_SEATS, headers=admin_headers(),
    )
    game_id = response.json()["game_id"]

    result = await client.get(
        f"/api/admin/games/{game_id}/stream", params={"t": "not-the-token"},
    )
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "forbidden_admin"


async def test_the_admin_stream_rejects_a_missing_token(client):
    """No credential at all is the same 403."""
    response = await client.post(
        "/api/admin/games", json=FOUR_HUMAN_SEATS, headers=admin_headers(),
    )
    game_id = response.json()["game_id"]

    assert (await client.get(f"/api/admin/games/{game_id}/stream")).status_code == 403


async def test_a_command_route_does_not_accept_a_query_token(client):
    """Only the read-only stream takes ``?t=``.

    A token that could reach a mutating route through a URL would be a token
    that could be created, started or abandoned with by anyone the link was
    forwarded to.
    """
    result = await client.post(
        "/api/admin/games", json=FOUR_HUMAN_SEATS, params={"t": ADMIN_TOKEN},
    )
    assert result.status_code == 403


async def test_defaults_require_the_admin_token(client):
    """The names on a configured table are the operator's own household."""
    response = await client.get("/api/admin/defaults")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_admin"


async def test_defaults_report_the_configured_table(client, container):
    """The console fills its setup form from this (§10.4)."""
    container.settings.table = TableDefaults(
        ns="Us",
        ew="Them",
        seats={
            "NORTH": SeatDefault(name="Mary", type="human"),
            "EAST": SeatDefault(name="East", type="computer"),
            "SOUTH": SeatDefault(name="Phil", type="human"),
            "WEST": SeatDefault(name="West", type="computer"),
        },
    )

    response = await client.get("/api/admin/defaults", headers=admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["teams"] == {"ns": "Us", "ew": "Them"}
    assert body["seats"][0] == {"seat": "NORTH", "name": "Mary", "type": "human"}
    assert [s["seat"] for s in body["seats"]] == ["NORTH", "EAST", "SOUTH", "WEST"]


async def test_defaults_report_the_built_in_table_when_nothing_is_configured(
    client, container,
):
    """An operator who has set nothing still gets a usable form."""
    response = await client.get("/api/admin/defaults", headers=admin_headers())
    body = response.json()
    assert body["teams"] == {"ns": DEFAULT_TEAM_NS, "ew": DEFAULT_TEAM_EW}
    assert {s["seat"]: (s["name"], s["type"]) for s in body["seats"]} == DEFAULT_SEATS
