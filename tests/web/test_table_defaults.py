# tests.web.test_table_defaults
import os
from html.parser import HTMLParser
from pathlib import Path

import pytest

import pinochle.web.container as container
from pinochle.web.container import (
    DEFAULT_SEATS,
    DEFAULT_TEAM_EW,
    DEFAULT_TEAM_NS,
    Settings,
    TableDefaults,
)

ROOT = Path(__file__).resolve().parents[2]

# Every variable the server reads. A setting added without a line in
# .env.example is a setting nobody can discover, which is what this pins.
DOCUMENTED_KEYS = {
    "PINOCHLE_TEAM_NS",
    "PINOCHLE_TEAM_EW",
    *(
        f"PINOCHLE_SEAT_{seat}_{field}"
        for seat in ("NORTH", "EAST", "SOUTH", "WEST")
        for field in ("NAME", "TYPE")
    ),
    "PINOCHLE_ADMIN_TOKEN",
    "PINOCHLE_PUBLIC_BASE_URL",
    "PINOCHLE_CARD_BACK",
    "PINOCHLE_TRICK_CLEAR_SECONDS",
    "PINOCHLE_COMPUTER_DELAY_SECONDS",
    "PINOCHLE_SSE_KEEPALIVE_SECONDS",
    "PINOCHLE_SSE_QUEUE_MAXSIZE",
    "PINOCHLE_SHUFFLE_SEED",
    "PINOCHLE_FRONTEND_DIR",
    "PINOCHLE_LOG_LEVEL",
}


@pytest.fixture
def clean_env(monkeypatch):
    """Present an environment that configures nothing at all.

    Both halves matter. The variables go, so that a default really is a
    default; and ``load_dotenv`` is stubbed out, because a developer with a
    real ``.env`` beside the project would otherwise have it read into the
    middle of these tests and get different answers from everybody else.
    """
    for key in [k for k in os.environ if k.startswith("PINOCHLE_")]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(container, "load_dotenv", lambda *a, **k: False)


def test_an_unconfigured_table_is_the_built_in_one(clean_env):
    """An environment that says nothing leaves every default in place."""
    table = TableDefaults.from_env()
    assert (table.ns, table.ew) == (DEFAULT_TEAM_NS, DEFAULT_TEAM_EW)
    assert {s: (d.name, d.type) for s, d in table.seats.items()} == DEFAULT_SEATS


def test_a_configured_seat_replaces_only_itself(clean_env, monkeypatch):
    """What the file sets is used; what it leaves out keeps its default."""
    monkeypatch.setenv("PINOCHLE_SEAT_NORTH_NAME", "Mary")
    monkeypatch.setenv("PINOCHLE_SEAT_NORTH_TYPE", "human")
    monkeypatch.setenv("PINOCHLE_TEAM_NS", "Us")

    table = TableDefaults.from_env()
    assert table.seats["NORTH"] == type(table.seats["NORTH"])(name="Mary", type="human")
    assert table.ns == "Us"
    assert table.ew == DEFAULT_TEAM_EW, "an unset team keeps its default"
    assert table.seats["EAST"].name == "East", "an unset seat keeps its default"


def test_a_blank_setting_is_not_a_name(clean_env, monkeypatch):
    """``PINOCHLE_SEAT_EAST_NAME=`` means unset, not a seat with no name."""
    monkeypatch.setenv("PINOCHLE_SEAT_EAST_NAME", "   ")
    assert TableDefaults.from_env().seats["EAST"].name == "East"


def test_a_seat_played_by_neither_is_refused(clean_env, monkeypatch):
    """Caught at startup, not at the first game the operator tries to create."""
    monkeypatch.setenv("PINOCHLE_SEAT_WEST_TYPE", "robot")
    with pytest.raises(ValueError, match="PINOCHLE_SEAT_WEST_TYPE"):
        TableDefaults.from_env()


def test_settings_carries_the_table(clean_env):
    """``Settings.from_env`` reads the table along with everything else."""
    assert Settings.from_env().table.seats["SOUTH"].type == "human"


def test_env_example_documents_every_setting():
    """A setting with no line in .env.example is one nobody can discover."""
    documented = keys_in(ROOT / ".env.example")
    assert documented == DOCUMENTED_KEYS


def test_env_example_specifies_nothing():
    """Every key is commented out, so that copying the file changes nothing.

    The file shows each default beside its key; uncommenting one is how an
    operator says they want something other than the default.
    """
    live = [
        line for line in (ROOT / ".env.example").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert live == []


def test_the_console_form_starts_out_holding_the_same_defaults():
    """admin.html's own values must agree with the ones the server sends.

    The form has to be sensible before it has asked the server anything --
    the console can only ask once it has an admin token -- so the defaults
    exist in both places. Two copies that could disagree are worth a test.
    """
    form = parse_setup_form(ROOT / "frontend" / "public" / "admin.html")
    assert form["team-ns"] == DEFAULT_TEAM_NS
    assert form["team-ew"] == DEFAULT_TEAM_EW
    for seat, (name, kind) in DEFAULT_SEATS.items():
        assert form[f"name-{seat}"] == name
        assert form[f"type-{seat}"] == kind


def keys_in(path: Path) -> set[str]:
    """Return every PINOCHLE_ key the example file mentions, set or commented."""
    keys = set()
    for line in path.read_text().splitlines():
        stripped = line.lstrip("#").strip()
        name, sep, _ = stripped.partition("=")
        if sep and name.startswith("PINOCHLE_") and " " not in name:
            keys.add(name)
    return keys


class _SetupForm(HTMLParser):
    """Collect the setup form's starting values, by control name."""

    def __init__(self):
        super().__init__()
        self.values: dict[str, str] = {}
        self._select: str | None = None

    def handle_starttag(self, tag, attrs):
        """Record an input's value, and a select's selected option."""
        attributes = dict(attrs)
        if tag == "input" and "name" in attributes:
            self.values[attributes["name"]] = attributes.get("value", "")
        elif tag == "select":
            self._select = attributes.get("name")
        elif tag == "option" and self._select and "selected" in attributes:
            self.values[self._select] = attributes.get("value", "")

    def handle_endtag(self, tag):
        """Leave the select whose options were being read."""
        if tag == "select":
            self._select = None


def parse_setup_form(path: Path) -> dict[str, str]:
    """Return the console form's control names and their starting values."""
    parser = _SetupForm()
    parser.feed(path.read_text())
    return parser.values
