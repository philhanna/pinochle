# tests.web.test_pages
from pinochle.web.container import SeatDefault, TableDefaults
from tests.web.conftest import ADMIN_TOKEN, FRONTEND_DIR


async def test_healthz_reports_ok(client):
    """The container health check has to answer before anything else does."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_the_root_serves_the_player_page(client):
    """A player who opens the bare URL still gets the table, then is told to join."""
    response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    # The containers the client renders into; the page ships no table markup of
    # its own, since everything on it is drawn from the event stream (RT-5).
    for container in ("stage", "felt", "centre", "scoreboard", "hand", "panel"):
        assert f'id="{container}"' in response.text


async def test_a_join_link_serves_the_same_page(client):
    """The seat is resolved in the browser from ``?t=``, not by the server (D1)."""
    response = await client.get("/join/some-game-id", params={"t": "a-token"})
    assert response.status_code == 200
    assert response.text == (FRONTEND_DIR / "public" / "index.html").read_text()


async def test_the_admin_path_serves_the_console_page(client):
    """Slice A2 fills this page in; the route and the file exist now."""
    response = await client.get("/admin")
    assert response.status_code == 200
    assert "Pinochle console" in response.text


async def test_authenticated_console_is_prefilled_before_its_first_render(
    client, container,
):
    """The HTML response itself carries the table configured in ``.env``."""
    container.settings.table = TableDefaults(
        ns="Boys & Co.",
        ew="Girls",
        seats={
            "NORTH": SeatDefault(name="John", type="human"),
            "EAST": SeatDefault(name="Ellie", type="computer"),
            "SOUTH": SeatDefault(name="Dad", type="human"),
            "WEST": SeatDefault(name='Mom "M"', type="computer"),
        },
    )

    response = await client.get("/admin", params={"t": ADMIN_TOKEN})

    assert response.status_code == 200
    assert f'name="admin-token" type="password"\n               value="{ADMIN_TOKEN}"' in response.text
    assert 'name="team-ns" value="Boys &amp; Co."' in response.text
    assert 'name="name-NORTH" value="John"' in response.text
    assert 'name="name-WEST" value="Mom &quot;M&quot;"' in response.text
    north = response.text.split('name="type-NORTH"', 1)[1].split("</select>", 1)[0]
    assert '<option value="human" selected>' in north
    assert '<option value="computer" selected>' not in north


async def test_bare_console_is_prefilled_without_disclosing_the_admin_token(
    client, container,
):
    """Table defaults need no query token, but the credential remains secret."""
    container.settings.table = TableDefaults(
        ns="Configured NS",
        ew="Configured EW",
        seats={
            seat: SeatDefault(name=f"Configured {seat}", type="human")
            for seat in ("NORTH", "EAST", "SOUTH", "WEST")
        },
    )

    response = await client.get("/admin")

    assert 'name="team-ns" value="Configured NS"' in response.text
    assert 'name="name-NORTH" value="Configured NORTH"' in response.text
    assert 'name="admin-token" type="password"\n               value=""' in response.text


async def test_the_page_loads_its_module_from_the_compiled_output(client):
    """ARC-8: the browser loads what tsc emitted, with no bundler in between."""
    response = await client.get("/")
    assert '<script type="module" src="/static/main.js">' in response.text


async def test_the_stylesheets_are_served_from_the_public_mount(client):
    """``/assets`` is the hand-written half of the front end."""
    for sheet in ("table.css", "style.css"):
        response = await client.get(f"/assets/{sheet}")
        assert response.status_code == 200, sheet
        assert response.headers["content-type"].startswith("text/css")


async def test_the_client_is_served_for_revalidation_rather_than_reuse(client):
    """An edited stylesheet or module has to reach a browser that has the old one.

    Nothing in the front end is named with a content hash (ARC-8 — no bundler),
    so without this a browser is free to go on serving a cached client from its
    own store and never ask.  The card artwork is the opposite case and is
    cached hard on purpose (see test_cards_router).
    """
    for path in ("/", "/admin", "/assets/table.css", "/static/main.js"):
        response = await client.get(path)
        assert response.status_code == 200, path
        assert response.headers["cache-control"] == "no-cache", path


async def test_the_table_page_loads_the_table_stylesheet(client):
    """The console and the table are styled separately; neither drags in the other."""
    assert "/assets/table.css" in (await client.get("/")).text
    assert "/assets/style.css" in (await client.get("/admin")).text


async def test_the_admin_stream_guard_accepts_a_query_token(container):
    """§6.2: the console opens this with ``EventSource``, which sets no headers.

    Asserted against the guard rather than over HTTP: the stream never ends,
    so a test that opened it through the client would hang on close — which
    is why the stream tests drive the route functions directly.
    """
    from fastapi import Request

    from pinochle.web.dependencies import require_admin_stream
    from pinochle.web.main import create_app
    from tests.web.conftest import ADMIN_TOKEN

    app = create_app(container)
    request = Request({
        "type": "http", "method": "GET", "path": "/", "headers": [],
        "query_string": f"t={ADMIN_TOKEN}".encode(), "app": app,
    })

    assert require_admin_stream(request) is None
