# tests.web.test_pages
from tests.web.conftest import FRONTEND_DIR


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
