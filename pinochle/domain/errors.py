# pinochle.domain.errors


class PinochleError(Exception):
    """Base class for every error a Pinochle rule or lookup can raise.

    Subclasses distinguish the different ways a player or administrator
    action can be rejected, so that the web layer can map failures to HTTP
    status codes without string-matching exception messages.
    """


class UnknownGameError(PinochleError):
    """Raised when a game id does not identify any known game."""


class NotYourTurnError(PinochleError):
    """Raised when the right phase was acted on by the wrong seat."""


class WrongPhaseError(PinochleError):
    """Raised when an action does not belong in the game's current phase."""


class IllegalActionError(PinochleError):
    """Raised when an action is not legal on its own terms.

    Covers an illegal card, an invalid bid, the wrong number of cards
    passed, or a position already taken — as distinct from acting in the
    wrong phase or out of turn.
    """


class SetupError(PinochleError):
    """Raised when setup is not complete enough for the requested transition."""
