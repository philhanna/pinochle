# tests.adapters.test_fake_scheduler
from pinochle.adapters.fake_scheduler import FakeScheduler


def test_callback_does_not_run_before_its_due_time():
    """A pending callback must not fire until the clock reaches it."""
    scheduler = FakeScheduler()
    calls = []
    scheduler.call_later(1.5, lambda: calls.append("fired"))

    scheduler.advance(1.0)
    assert calls == []


def test_callback_runs_once_its_due_time_is_reached():
    """Advancing past the due time runs the callback exactly once."""
    scheduler = FakeScheduler()
    calls = []
    scheduler.call_later(1.5, lambda: calls.append("fired"))

    scheduler.advance(1.0)
    scheduler.advance(0.5)
    assert calls == ["fired"]

    scheduler.advance(10.0)
    assert calls == ["fired"]


def test_due_callbacks_run_in_due_order():
    """Several callbacks due by the same advance run earliest-first."""
    scheduler = FakeScheduler()
    order = []
    scheduler.call_later(2.0, lambda: order.append("second"))
    scheduler.call_later(1.0, lambda: order.append("first"))

    scheduler.advance(2.0)
    assert order == ["first", "second"]


def test_a_callback_scheduled_during_advance_waits_for_the_next_call():
    """A zero-delay reschedule from within a callback needs its own advance().

    This mirrors AsyncioScheduler always deferring by at least one tick, so
    a chain of zero-delay computer moves runs one advance() at a time rather
    than draining itself within a single call.
    """
    scheduler = FakeScheduler()
    order = []

    def second():
        order.append("second")

    def first():
        order.append("first")
        scheduler.call_later(0, second)

    scheduler.call_later(0, first)
    scheduler.advance(0)
    assert order == ["first"]

    scheduler.advance(0)
    assert order == ["first", "second"]
