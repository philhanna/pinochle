# tests.domain.test_hold
import pytest

from pinochle.domain.hold import Hold, HoldReason


def test_timed_hold_ends_by_the_clock():
    """A timed hold carries its interval and offers a player nothing to do."""
    hold = Hold.timed(1, HoldReason.TRICK_CLEAR, 1.5)
    assert hold.seconds == 1.5
    assert hold.ackable is False


def test_released_hold_waits_indefinitely():
    """A hold awaiting a player has no interval at all (RT-13)."""
    hold = Hold.awaiting_release(2, HoldReason.ROUND_SCORED)
    assert hold.seconds is None
    assert hold.ackable is True


def test_hold_with_neither_ending_is_rejected():
    """A hold that no clock and no player can end would stop the game forever."""
    with pytest.raises(ValueError, match="not both and not neither"):
        Hold(id=3, reason=HoldReason.ROUND_SCORED)


def test_hold_with_both_endings_is_rejected():
    """RT-13 refuses a backstop interval on a hold that waits on a player.

    An interval there would resume the game while the players were still
    reading the notice the hold exists to let them read.
    """
    with pytest.raises(ValueError, match="not both and not neither"):
        Hold(id=4, reason=HoldReason.ROUND_SCORED, seconds=60.0, ackable=True)


@pytest.mark.parametrize("seconds", [0, -1.5])
def test_timed_hold_needs_a_positive_interval(seconds):
    """A pause of no length is not a pause; it is a missing event."""
    with pytest.raises(ValueError, match="positive interval"):
        Hold(id=5, reason=HoldReason.TRICK_CLEAR, seconds=seconds)


def test_hold_is_frozen():
    """A hold is a fact about the game's state, not a mutable handle on it."""
    hold = Hold.timed(6, HoldReason.THINKING, 1.0)
    with pytest.raises(Exception):
        hold.seconds = 2.0  # type: ignore[misc]
