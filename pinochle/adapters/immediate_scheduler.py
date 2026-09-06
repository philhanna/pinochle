# pinochle.adapters.immediate_scheduler
from typing import Callable

from pinochle.ports.scheduler_port import SchedulerPort


class ImmediateScheduler(SchedulerPort):
    """``SchedulerPort`` that ignores the delay and runs the callback at once.

    Collapses every timed pause to zero, which is what a headless run wants:
    tests and CLI drivers step through a whole game without waiting.  The
    asyncio-backed adapter that honours real delays arrives with the HTTP
    layer; until then this keeps the seam in place without any timing
    machinery behind it.
    """

    def call_later(self, delay_seconds: float, callback: Callable[[], None]) -> None:
        """Invoke ``callback`` synchronously, disregarding ``delay_seconds``."""
        callback()
