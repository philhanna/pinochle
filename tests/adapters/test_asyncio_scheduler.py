# tests.adapters.test_asyncio_scheduler
import asyncio

from pinochle.adapters.asyncio_scheduler import AsyncioScheduler


async def test_call_later_runs_after_the_delay():
    """A positive delay should run the callback on the loop, eventually."""
    scheduler = AsyncioScheduler()
    calls = []
    scheduler.call_later(0.01, lambda: calls.append("fired"))

    assert calls == []
    await asyncio.sleep(0.05)
    assert calls == ["fired"]


async def test_zero_delay_still_defers_to_a_later_tick():
    """A zero (or negative) delay must not run the callback synchronously.

    The computer driver relies on this: acting immediately inside
    call_later(0, ...) would re-enter an in-flight load/dispatch/save cycle.
    """
    scheduler = AsyncioScheduler()
    calls = []
    scheduler.call_later(0, lambda: calls.append("fired"))

    # Nothing has run yet: call_soon only queues the callback for the loop.
    assert calls == []
    await asyncio.sleep(0)
    assert calls == ["fired"]
