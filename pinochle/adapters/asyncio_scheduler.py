# pinochle.adapters.asyncio_scheduler
import asyncio
from typing import Callable

from pinochle.ports.scheduler_port import SchedulerPort


class AsyncioScheduler(SchedulerPort):
    """``SchedulerPort`` backed by the running asyncio event loop.

    Used in production once the web layer is wired: every timed pause is
    counted by ``loop.call_later``, running on the same thread as every
    request handler so nothing races a mutation of the single in-memory
    ``Game`` (§4.7).
    """

    def call_later(self, delay_seconds: float, callback: Callable[[], None]) -> None:
        """Invoke ``callback`` after ``delay_seconds`` on the running loop.

        A non-positive delay still defers to a later tick via
        ``loop.call_soon`` rather than running synchronously: a computer
        driver relies on that deferral to avoid re-entering an in-flight
        load/dispatch/save cycle even when the configured delay is zero.
        """
        loop = asyncio.get_running_loop()
        if delay_seconds <= 0:
            loop.call_soon(callback)
        else:
            loop.call_later(delay_seconds, callback)
