# pinochle.web.container
import os
import secrets
from dataclasses import dataclass
from random import Random

from pinochle.adapters.asyncio_scheduler import AsyncioScheduler
from pinochle.adapters.composite_notification import CompositeNotification
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.adapters.in_memory_seat_tokens import InMemorySeatTokens
from pinochle.adapters.logging_notification import LoggingNotification
from pinochle.adapters.sse_notification import SseNotification
from pinochle.ports.admin_port import AdminPort
from pinochle.ports.game_state_port import GameStatePort
from pinochle.ports.notification_port import NotificationPort
from pinochle.ports.player_action_port import PlayerActionPort
from pinochle.ports.scheduler_port import SchedulerPort
from pinochle.ports.seat_token_port import SeatTokenPort
from pinochle.services.computer_driver import ComputerDriver
from pinochle.services.game_service import GameService
from pinochle.strategies.computer_player_strategy import ComputerPlayerStrategy


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
    admin_token_generated: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from ``PINOCHLE_*`` environment variables.

        ``PINOCHLE_ADMIN_TOKEN`` is generated when it isn't set —
        ``admin_token_generated`` tells the caller to log it (§9.1: an
        operator running one game for an evening reads it from the
        container log rather than setting it explicitly).
        """
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
    rng = Random(settings.shuffle_seed) if settings.shuffle_seed is not None else None
    service = GameService(
        state, notifier, scheduler,
        rng=rng, trick_clear_seconds=settings.trick_clear_seconds,
    )
    driver = ComputerDriver(
        service, state, scheduler, ComputerPlayerStrategy(),
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
    )
