# tests.web.test_pages
from tests.web.conftest import FRONTEND_DIR


async def test_healthz_reports_ok(client):
    """The container health check has to answer before anything else does."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_the_root_serves_the_player_page(client):
    """A player who opens the bare URL still gets the page, then is told to join."""
    response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<main id=\"app\">" in response.text


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


async def test_the_stylesheet_is_served_from_the_public_mount(client):
    """``/assets`` is the hand-written half of the front end."""
    response = await client.get("/assets/style.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
