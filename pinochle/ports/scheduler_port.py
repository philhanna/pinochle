# pinochle.ports.scheduler_port
from abc import ABC, abstractmethod
from typing import Callable


class SchedulerPort(ABC):
    """Secondary port for deferring work until a later moment.

    Every timed pause in the game — the meld display, the trick-clear
    interval, and the computer-move delay — is owned and counted by the
    server.  The application layer expresses those delays through this port
    so that it never imports ``asyncio`` or ``time.sleep`` directly, keeping
    the core free of a concrete timing mechanism.

    Implementations may run the callback on an event loop, on a thread, or
    immediately.  Tests use a fake that advances a virtual clock on demand,
    so that a suite never waits in real time for a pause to elapse.
    """

    @abstractmethod
    def call_later(self, delay_seconds: float, callback: Callable[[], None]) -> None:
        """Invoke ``callback`` once, after at least ``delay_seconds`` have passed."""
