# tests.web.test_main
import logging

from pinochle.adapters.fake_scheduler import FakeScheduler
from pinochle.web.container import Settings, build_container
from pinochle.web.main import create_app


async def test_lifespan_logs_the_generated_admin_token(caplog):
    """§9.1: an operator with no configured token reads it from the log."""
    caplog.set_level(logging.WARNING, logger="pinochle")
    settings = Settings(admin_token="generated-value", admin_token_generated=True)
    container = build_container(settings, scheduler=FakeScheduler())
    app = create_app(container)

    async with app.router.lifespan_context(app):
        pass

    assert any("generated-value" in record.message for record in caplog.records)


async def test_lifespan_is_silent_when_the_token_was_configured(caplog):
    """No warning should be logged when the operator set their own token."""
    caplog.set_level(logging.WARNING, logger="pinochle")
    settings = Settings(admin_token="explicit-token", admin_token_generated=False)
    container = build_container(settings, scheduler=FakeScheduler())
    app = create_app(container)

    async with app.router.lifespan_context(app):
        pass

    assert caplog.records == []


async def test_lifespan_logs_the_env_file_it_read(caplog):
    """An operator can see which ``.env`` the settings came from."""
    caplog.set_level(logging.INFO, logger="pinochle")
    settings = Settings(admin_token="explicit-token", dotenv_path="/srv/pinochle/.env")
    container = build_container(settings, scheduler=FakeScheduler())
    app = create_app(container)

    async with app.router.lifespan_context(app):
        pass

    assert any("/srv/pinochle/.env" in record.message for record in caplog.records)


async def test_lifespan_says_nothing_when_no_env_file_was_read(caplog):
    """Nothing to announce when the environment alone configured the run."""
    caplog.set_level(logging.INFO, logger="pinochle")
    settings = Settings(admin_token="explicit-token", dotenv_path=None)
    container = build_container(settings, scheduler=FakeScheduler())
    app = create_app(container)

    async with app.router.lifespan_context(app):
        pass

    assert caplog.records == []
