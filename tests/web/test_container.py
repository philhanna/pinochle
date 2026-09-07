# tests.web.test_container
from pinochle.web.container import Settings


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
