# tests.web.test_container
import os

import pytest

from pinochle.web import container
from pinochle.web.container import Settings, build_container


def test_from_env_generates_a_token_when_none_is_set(monkeypatch):
    """§9.1: no PINOCHLE_ADMIN_TOKEN means one is minted for this run."""
    monkeypatch.delenv("PINOCHLE_ADMIN_TOKEN", raising=False)
    settings = Settings.from_env()
    assert settings.admin_token
    assert settings.admin_token_generated is True


def test_from_env_uses_the_configured_token_when_set(monkeypatch):
    """An explicit token should be used as-is and not flagged as generated."""
    monkeypatch.setenv("PINOCHLE_ADMIN_TOKEN", "explicit-token")
    settings = Settings.from_env()
    assert settings.admin_token == "explicit-token"
    assert settings.admin_token_generated is False


def test_from_env_reads_the_configurable_delays(monkeypatch):
    """Docker/VPS operators tune these per design.md §10.4."""
    monkeypatch.setenv("PINOCHLE_ADMIN_TOKEN", "tok")
    monkeypatch.setenv("PINOCHLE_TRICK_CLEAR_SECONDS", "0.5")
    monkeypatch.setenv("PINOCHLE_COMPUTER_DELAY_SECONDS", "0")
    monkeypatch.setenv("PINOCHLE_SHUFFLE_SEED", "42")
    settings = Settings.from_env()
    assert settings.trick_clear_seconds == 0.5
    assert settings.computer_delay_seconds == 0
    assert settings.shuffle_seed == 42


def test_from_env_defaults_the_card_back(monkeypatch):
    """With nothing configured, the table is dealt with the blue back."""
    monkeypatch.delenv("PINOCHLE_CARD_BACK", raising=False)
    monkeypatch.setattr(container, "load_dotenv", lambda: None)
    assert Settings.from_env().card_back == "blue"


@pytest.mark.parametrize("configured,expected", [
    ("castle", "castle"),
    ("castle.svg", "castle"),
    ("castle.PNG", "castle"),
    ("  frog  ", "frog"),
    ("Astronaut", "astronaut"),
    ("", "blue"),
])
def test_from_env_reads_the_card_back_as_a_plain_file_name(monkeypatch, configured, expected):
    """The setting names a file in the backs directory — extension optional."""
    monkeypatch.setattr(container, "load_dotenv", lambda: None)
    monkeypatch.setenv("PINOCHLE_CARD_BACK", configured)
    assert Settings.from_env().card_back == expected


@pytest.mark.parametrize("configured", [
    "backs/castle.svg",
    "/app/pinochle/card_images/backs/castle.svg",
    "..\\castle",
    "no such back",
])
def test_a_card_back_that_is_not_a_plain_file_name_is_refused(monkeypatch, configured):
    """A path is refused at startup rather than 404ing on the first deal."""
    monkeypatch.setattr(container, "load_dotenv", lambda: None)
    monkeypatch.setenv("PINOCHLE_CARD_BACK", configured)
    with pytest.raises(ValueError):
        Settings.from_env()


def test_the_card_back_may_be_set_in_a_dotenv_file(monkeypatch):
    """``.env`` is read before the environment is inspected, not after."""
    monkeypatch.setenv("PINOCHLE_CARD_BACK", "blue")
    monkeypatch.setattr(
        container, "load_dotenv",
        lambda: os.environ.__setitem__("PINOCHLE_CARD_BACK", "castle"),
    )
    assert Settings.from_env().card_back == "castle"


def test_the_configured_back_is_what_the_adapter_serves():
    """Settings carry the name; the adapter turns it into a path (ARC-4)."""
    built = build_container(Settings(admin_token="tok", card_back="castle"))
    assert built.cards.get_back_path().endswith("castle.svg")


def test_from_env_records_the_env_file_it_read(monkeypatch):
    """The path is kept so startup can log it once logging is configured."""
    monkeypatch.setattr(container, "find_dotenv", lambda: "/srv/pinochle/.env")
    monkeypatch.setattr(container, "load_dotenv", lambda: True)
    assert Settings.from_env().dotenv_path == "/srv/pinochle/.env"


def test_from_env_records_no_env_file_when_none_was_read(monkeypatch):
    """No file found means nothing for startup to announce."""
    monkeypatch.setattr(container, "find_dotenv", lambda: "")
    monkeypatch.setattr(container, "load_dotenv", lambda: False)
    assert Settings.from_env().dotenv_path is None
