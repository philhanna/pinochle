# pinochle.domain.hold
from dataclasses import dataclass
from enum import Enum, auto


class HoldReason(Enum):
    """Why the game is holding, and therefore what the notice area says (UI-19).

    The reason travels to the client, which turns it into words of its own
    (UI-19 puts the wording on that side).  So this is the shared vocabulary
    of the two halves, and a reason added here without a sentence to match it
    on the client is a hold the table cannot explain.
    """

    TRICK_CLEAR = auto()
    THINKING = auto()
    DRAW_TIED = auto()
    DEALER_SELECTED = auto()
    ROUND_ABANDONED = auto()
    ROUND_SCORED = auto()


@dataclass(frozen=True)
class Hold:
    """A pause the game is occupying, owned and counted by the server (RT-13).

    RT-9 is the point of the type: a pause is a state the game is in, not an
    effect the interface plays.  While a hold is up, an action that would
    advance past it is refused exactly as any other out-of-phase action, so
    four clients driven from one clock cannot get out of step with each other
    (RT-11).

    A hold ends in exactly one of two ways, and which one is settled when it
    begins:

    - after ``seconds``, counted by the server's scheduler (UI-15's trick
      clear is this kind);
    - when a player releases it, which any one seated player may do.

    The two are deliberately exclusive.  Giving a hold that waits on a player
    an interval as well would undo the control it was attached to, resuming
    the game while the players are still talking about what the notice says;
    RT-13 says so, and ``__post_init__`` is where that decision is enforced
    rather than merely documented.  A table where nobody is left to release a
    hold is RT-12's case, not this one's.

    Attributes:
        id: Identifies this hold, so that releasing it can name it.  A release
            naming a hold that has already ended is a no-op rather than an
            error (RT-13), which is what makes two players clicking at the
            same moment harmless.
        reason: What the table is being held for.
        seconds: How long the pause lasts, for a timed hold; ``None`` for one
            that waits on a player.
        ackable: Whether a player may release it.
    """

    id: int
    reason: HoldReason
    seconds: float | None = None
    ackable: bool = False

    def __post_init__(self) -> None:
        """Reject a hold that could never end, or that could end two ways."""
        if self.ackable == (self.seconds is not None):
            raise ValueError(
                "a hold ends either after an interval or on a player's release, "
                f"not both and not neither: {self.reason.name}"
            )
        if self.seconds is not None and self.seconds <= 0:
            raise ValueError(f"a timed hold needs a positive interval: {self.seconds}")

    @classmethod
    def timed(cls, id: int, reason: HoldReason, seconds: float) -> "Hold":
        """A hold the server ends by the clock, with nothing for a player to do."""
        return cls(id=id, reason=reason, seconds=seconds)

    @classmethod
    def awaiting_release(cls, id: int, reason: HoldReason) -> "Hold":
        """A hold that waits, for as long as it takes, for any seat to release it."""
        return cls(id=id, reason=reason, ackable=True)
