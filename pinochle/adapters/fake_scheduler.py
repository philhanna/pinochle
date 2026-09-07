# pinochle.adapters.fake_scheduler
from typing import Callable

from pinochle.ports.scheduler_port import SchedulerPort


class FakeScheduler(SchedulerPort):
    """``SchedulerPort`` driven by a virtual clock instead of real time.

    Tests advance the clock explicitly with ``advance()`` rather than
    sleeping, so a suite never waits in real time for a pause to elapse
    (ARC-10).  A single ``advance()`` call only runs the callbacks that were
    already pending and are now due; a callback that reschedules another one
    for the same instant needs a further ``advance()`` call to run it — this
    matches how ``AsyncioScheduler`` always defers by at least one tick, so
    a zero-delay chain of computer moves runs at "as fast as the loop can
    turn" rather than all within one synchronous call.
    """

    def __init__(self):
        """Start the virtual clock at zero with nothing scheduled."""
        self._now = 0.0
        self._pending: list[tuple[float, Callable[[], None]]] = []

    def call_later(self, delay_seconds: float, callback: Callable[[], None]) -> None:
        """Record ``callback`` to run once the clock reaches ``delay_seconds`` from now."""
        self._pending.append((self._now + delay_seconds, callback))

    def advance(self, seconds: float = 0.0) -> None:
        """Move the clock forward and run whatever was already due.

        Only callbacks pending before this call are considered, sorted by
        due time; anything a callback schedules during this call is left for
        the next ``advance()``.
        """
        self._now += seconds
        due = sorted(
            (item for item in self._pending if item[0] <= self._now),
            key=lambda item: item[0],
        )
        for item in due:
            self._pending.remove(item)
            _, callback = item
            callback()
