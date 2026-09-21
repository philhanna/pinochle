# pinochle.web.container
import os
import re
import secrets
from dataclasses import dataclass, field
from random import Random

from dotenv import find_dotenv, load_dotenv

from pinochle.adapters.asyncio_scheduler import AsyncioScheduler
from pinochle.adapters.composite_notification import CompositeNotification
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.adapters.in_memory_seat_tokens import InMemorySeatTokens
from pinochle.adapters.logging_notification import LoggingNotification
from pinochle.adapters.sse_notification import SseNotification
from pinochle.adapters.svg_card_image import SvgCardImage
from pinochle.ports.admin_port import AdminPort
from pinochle.ports.card_image_port import CardImagePort
from pinochle.ports.game_state_port import GameStatePort
from pinochle.ports.notification_port import NotificationPort
from pinochle.ports.player_action_port import PlayerActionPort
from pinochle.ports.scheduler_port import SchedulerPort
from pinochle.ports.seat_token_port import SeatTokenPort
from pinochle.services.computer_driver import ComputerDriver
from pinochle.services.game_service import GameService
from pinochle.strategies.computer_player_strategy import ComputerPlayerStrategy


# The table the console offers when the environment says nothing about it.
# These are the values the setup form is born with, and they are repeated in
# frontend/public/admin.html so the form is sensible before it has asked the
# server anything; a test holds the two copies to each other.
DEFAULT_TEAM_NS = "North-South"
DEFAULT_TEAM_EW = "East-West"
DEFAULT_SEATS = {
    "NORTH": ("North", "computer"),
    "EAST": ("East", "computer"),
    "SOUTH": ("South", "human"),
    "WEST": ("West", "computer"),
}


@dataclass(frozen=True)
class SeatDefault:
    """What one seat of the console's setup form starts out holding."""

    name: str
    type: str


@dataclass(frozen=True)
class TableDefaults:
    """The table the console's setup form is pre-filled with (§10.4).

    Every field is only a starting point: the operator edits the form before
    creating the game, and the game is made from what the form says, not from
    this.  What this changes is how much editing a regular table needs — a
    household that plays the same four seats every week configures them once
    in ``.env`` and stops retyping them.

    Attributes:
        ns: The North-South partnership's name.
        ew: The East-West partnership's name.
        seats: One entry per seat name (``NORTH``…``WEST``), in table order.
    """

    ns: str
    ew: str
    seats: dict[str, SeatDefault]

    @classmethod
    def from_env(cls) -> "TableDefaults":
        """Read the table defaults from ``PINOCHLE_TEAM_*`` and ``PINOCHLE_SEAT_*``.

        A variable the file does not set keeps its built-in default, so an
        operator configures the seats they care about and leaves the rest.
        """
        return cls(
            ns=os.environ.get("PINOCHLE_TEAM_NS", DEFAULT_TEAM_NS).strip() or DEFAULT_TEAM_NS,
            ew=os.environ.get("PINOCHLE_TEAM_EW", DEFAULT_TEAM_EW).strip() or DEFAULT_TEAM_EW,
            seats={
                seat: SeatDefault(
                    name=os.environ.get(f"PINOCHLE_SEAT_{seat}_NAME", name).strip() or name,
                    type=_seat_type(
                        seat, os.environ.get(f"PINOCHLE_SEAT_{seat}_TYPE", ""), kind),
                )
                for seat, (name, kind) in DEFAULT_SEATS.items()
            },
        )


@dataclass
class Settings:
    """Configuration read once from the environment (design.md §10.4)."""

    admin_token: str
    public_base_url: str = "http://localhost:8000"
    trick_clear_seconds: float = 1.5
    computer_delay_seconds: float = 1.0
    frontend_dir: str = "frontend"
    sse_keepalive_seconds: float = 15.0
    sse_queue_maxsize: int = 256
    shuffle_seed: int | None = None
    log_level: str = "INFO"
    card_back: str = "blue"
    admin_token_generated: bool = False
    dotenv_path: str | None = None
    table: TableDefaults = field(
        default_factory=lambda: TableDefaults(
            ns=DEFAULT_TEAM_NS,
            ew=DEFAULT_TEAM_EW,
            seats={
                seat: SeatDefault(name=name, type=kind)
                for seat, (name, kind) in DEFAULT_SEATS.items()
            },
        ),
    )

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from ``PINOCHLE_*`` environment variables.

        A ``.env`` file beside the project is read first, for the settings
        an operator edits rather than exports — the card back, say.  It
        never overrides a variable already in the environment, so the
        container's own configuration still wins over a stray file.

        ``PINOCHLE_ADMIN_TOKEN`` is generated when it isn't set —
        ``admin_token_generated`` tells the caller to log it (§9.1: an
        operator running one game for an evening reads it from the
        container log rather than setting it explicitly).

        ``dotenv_path`` records which file was read, if any, so startup can
        say so once logging exists — an operator wondering why a setting
        didn't take can see whether the file was found at all.  It is set
        only when the file was actually read.
        """
        dotenv_path = find_dotenv()
        loaded = load_dotenv()
        seed = os.environ.get("PINOCHLE_SHUFFLE_SEED")
        configured_token = os.environ.get("PINOCHLE_ADMIN_TOKEN")
        return cls(
            admin_token=configured_token or secrets.token_urlsafe(16),
            admin_token_generated=not configured_token,
            public_base_url=os.environ.get("PINOCHLE_PUBLIC_BASE_URL", "http://localhost:8000"),
            trick_clear_seconds=float(os.environ.get("PINOCHLE_TRICK_CLEAR_SECONDS", "1.5")),
            computer_delay_seconds=float(os.environ.get("PINOCHLE_COMPUTER_DELAY_SECONDS", "1.0")),
            frontend_dir=os.environ.get("PINOCHLE_FRONTEND_DIR", "frontend"),
            sse_keepalive_seconds=float(os.environ.get("PINOCHLE_SSE_KEEPALIVE_SECONDS", "15")),
            sse_queue_maxsize=int(os.environ.get("PINOCHLE_SSE_QUEUE_MAXSIZE", "256")),
            shuffle_seed=int(seed) if seed else None,
            log_level=os.environ.get("PINOCHLE_LOG_LEVEL", "INFO"),
            card_back=_card_back_name(os.environ.get("PINOCHLE_CARD_BACK", "")),
            dotenv_path=dotenv_path if loaded else None,
            table=TableDefaults.from_env(),
        )


@dataclass
class Container:
    """The wired object graph for one running process (design.md §4.6)."""

    settings: Settings
    admin: AdminPort
    actions: PlayerActionPort
    state: GameStatePort
    sse: SseNotification
    notifier: NotificationPort
    tokens: SeatTokenPort
    scheduler: SchedulerPort
    cards: CardImagePort


def build_container(
    settings: Settings | None = None, scheduler: SchedulerPort | None = None,
) -> Container:
    """Wire the object graph (design.md §4.6).

    ``actions`` is the computer driver, not the bare ``GameService`` —
    decorating every ``PlayerActionPort`` method so the web layer never has
    to know a seat is a computer.  The driver is appended to the composite
    notifier last, once it exists, so it observes every event the service
    publishes and can pump a computer seat's turn.  Tests pass a
    ``FakeScheduler`` here instead of the default ``AsyncioScheduler``, so a
    timed pause — the trick-clear wait or a computer's move delay — can be
    advanced on demand rather than waited out.
    """
    settings = settings or Settings.from_env()
    state = InMemoryGameState()
    tokens = InMemorySeatTokens()
    scheduler = scheduler or AsyncioScheduler()
    sse = SseNotification(queue_maxsize=settings.sse_queue_maxsize)
    notifier = CompositeNotification([sse, LoggingNotification()])
    # One source of randomness for the whole game, so that a seed reproduces
    # it exactly (NFR-7): the shuffle and the computers' dealer-selection
    # draws both draw from this stream.
    rng = Random(settings.shuffle_seed) if settings.shuffle_seed is not None else None
    service = GameService(
        state, notifier, scheduler,
        rng=rng, trick_clear_seconds=settings.trick_clear_seconds,
    )
    driver = ComputerDriver(
        service, state, scheduler, ComputerPlayerStrategy(rng=rng),
        delay_seconds=settings.computer_delay_seconds,
    )
    notifier.append(driver)
    return Container(
        settings=settings,
        admin=service,
        actions=driver,
        state=state,
        sse=sse,
        notifier=notifier,
        tokens=tokens,
        scheduler=scheduler,
        cards=SvgCardImage(default_back=settings.card_back),
    )


def _seat_type(seat: str, configured: str, fallback: str) -> str:
    """Return who plays a seat by default: ``"human"`` or ``"computer"``.

    Refused at startup rather than at the first game, for the same reason as
    the card back: a typo here would otherwise surface as the console quietly
    offering the wrong table, which an operator would read as the form having
    ignored their file.
    """
    name = configured.strip().lower()
    if not name:
        return fallback
    if name not in ("human", "computer"):
        raise ValueError(
            f"PINOCHLE_SEAT_{seat}_TYPE must be 'human' or 'computer', "
            f"not {configured!r}"
        )
    return name


def _card_back_name(configured: str) -> str:
    """Return the bare asset name of the configured card back.

    The setting names a file in the bundled ``backs/`` directory and nothing
    else: ``castle``, or ``castle.svg`` for an operator who thinks of it as a
    file.  The extension is dropped because the format is chosen per request
    (SVG or PNG), and the directory is the adapter's business, not the
    operator's — so anything with a path in it is refused here, at startup,
    rather than turning into a puzzling 404 on the first deal.
    """
    name = configured.strip()
    if not name:
        return "blue"
    if "/" in name or "\\" in name:
        raise ValueError(
            f"PINOCHLE_CARD_BACK must be a plain file name, not a path: {configured!r}"
        )
    name = re.sub(r"\.(svg|png)$", "", name, flags=re.IGNORECASE).lower()
    if not re.fullmatch(r"[a-z0-9_]{1,40}", name):
        raise ValueError(f"{configured!r} is not a valid card back name.")
    return name
