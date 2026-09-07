# pinochle.web.errors
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pinochle.domain.errors import (
    IllegalActionError,
    NotYourTurnError,
    PinochleError,
    SetupError,
    UnknownGameError,
    WrongPhaseError,
)

# Order matters: the first matching (status, code) pair wins, so a subclass
# checked before its base class would take precedence — none of these
# subclass one another, so plain isinstance order is safe here.
_STATUS_AND_CODE: list[tuple[type[PinochleError], int, str]] = [
    (UnknownGameError, 404, "unknown_game"),
    (NotYourTurnError, 409, "not_your_turn"),
    (WrongPhaseError, 409, "wrong_phase"),
    (IllegalActionError, 409, "illegal_action"),
    (SetupError, 409, "setup_incomplete"),
]


class ForbiddenError(Exception):
    """Raised when a request's admin or seat credential does not check out."""

    def __init__(self, code: str, message: str):
        """Record the §5.5 error code and a human-readable message."""
        super().__init__(message)
        self.code = code
        self.message = message


def register_error_handlers(app: FastAPI) -> None:
    """Register the handlers that turn a raised error into the §5.5 envelope."""

    @app.exception_handler(PinochleError)
    async def _handle_pinochle_error(request: Request, exc: PinochleError) -> JSONResponse:
        """Map a rule or lookup failure to its status code and JSON body."""
        status_code, code = _status_and_code(exc)
        return _envelope(status_code, code, str(exc))

    @app.exception_handler(ForbiddenError)
    async def _handle_forbidden_error(request: Request, exc: ForbiddenError) -> JSONResponse:
        """Map a failed admin or seat credential check to a 403."""
        return _envelope(403, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Report a malformed request body as a 422."""
        return _envelope(422, "invalid_request", str(exc))

    @app.exception_handler(ValueError)
    async def _handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        """Report an unparseable card/suit code as a 422 (design.md §5.5)."""
        return _envelope(422, "invalid_request", str(exc))


def _status_and_code(exc: PinochleError) -> tuple[int, str]:
    """Return the (status, code) pair for the most specific matching type."""
    for exc_type, status_code, code in _STATUS_AND_CODE:
        if isinstance(exc, exc_type):
            return status_code, code
    return 500, "internal_error"


def _envelope(status_code: int, code: str, message: str) -> JSONResponse:
    """Build the ``{"error": {"code", "message"}}`` body every failure returns."""
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})
