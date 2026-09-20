# pinochle.web.main
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pinochle.web.container import Container, build_container
from pinochle.web.errors import register_error_handlers
from pinochle.web.routers import admin, cards, player, stream


def create_app(container: Container | None = None) -> FastAPI:
    """Build the ASGI app, wiring in ``container`` or a freshly built one.

    Tests substitute a container built with a ``FakeScheduler`` and a seeded
    shuffle; production uses the default, which wires ``AsyncioScheduler``
    and reads configuration from the environment (§10.4).
    """
    container = container or build_container()
    app = FastAPI(title="Pinochle", lifespan=_lifespan(container))
    app.state.container = container

    register_error_handlers(app)
    app.include_router(admin.router)
    app.include_router(admin.stream_router)
    app.include_router(player.router)
    app.include_router(stream.router)
    app.include_router(cards.router)

    public_dir = Path(container.settings.frontend_dir) / "public"
    dist_dir = Path(container.settings.frontend_dir) / "dist"
    # public/ holds the hand-written HTML and CSS; dist/ holds the modules
    # tsc compiles from frontend/src (ARC-8 — no bundler, so the browser
    # loads them as ES modules exactly as emitted).
    if public_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=public_dir), name="assets")
    if dist_dir.is_dir():
        app.mount("/static", StaticFiles(directory=dist_dir), name="static")

    @app.get("/healthz")
    async def healthz() -> dict:
        """Report for the container health check (§10)."""
        return {"status": "ok"}

    @app.get("/")
    async def index():
        """Serve the player's table page."""
        return _serve_page(public_dir / "index.html")

    @app.get("/join/{game_id}")
    async def join(game_id: str):
        """Serve the same table page; the client reads ``?t=`` itself."""
        return _serve_page(public_dir / "index.html")

    @app.get("/admin")
    async def admin_page():
        """Serve the administrator's console."""
        return _serve_page(public_dir / "admin.html")

    return app


def _lifespan(container: Container):
    """Build the app's lifespan: configure logging once, at startup (§4.9).

    A single ``pinochle`` logger tree at ``PINOCHLE_LOG_LEVEL``, so
    ``action.accepted``/``action.rejected``/``event.published`` records
    (NFR-9) actually reach ``docker compose logs`` instead of being dropped
    by the default, unconfigured root logger.
    """
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(
            level=container.settings.log_level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        if container.settings.admin_token_generated:
            logging.getLogger("pinochle").warning(
                "No PINOCHLE_ADMIN_TOKEN was set; generated one for this run: %s",
                container.settings.admin_token,
            )
        yield

    return lifespan


def _serve_page(path: Path):
    """Serve a static front-end page, or a friendly 404 before it exists."""
    if not path.is_file():
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": (
                f"{path.name} is missing. Run `make build`, or check "
                "PINOCHLE_FRONTEND_DIR."
            )}},
        )
    return FileResponse(path)


app = create_app()
