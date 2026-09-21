# pinochle.web.schemas
from pydantic import BaseModel


class TeamsRequest(BaseModel):
    """The two partnership display names (§5.2)."""

    ns: str
    ew: str


class SeatRequest(BaseModel):
    """One seat's setup: which position, whose name, human or computer."""

    seat: str
    name: str
    type: str


class CreateGameRequest(BaseModel):
    """Body of ``POST /api/admin/games`` (§5.2)."""

    teams: TeamsRequest
    seats: list[SeatRequest]


class SeatResponse(BaseModel):
    """One seat's setup result, including its join link if it is human."""

    seat: str
    name: str
    type: str
    player_id: str
    join_url: str | None = None


class CreateGameResponse(BaseModel):
    """Response body of ``POST /api/admin/games`` (§5.2)."""

    game_id: str
    seats: list[SeatResponse]


class AbandonRequest(BaseModel):
    """Body of ``POST /api/admin/games/{id}/abandon``."""

    reason: str


class AcknowledgeRequest(BaseModel):
    """Body of ``POST /api/games/{id}/acknowledge``.

    The hold is named rather than left implicit so that a click which
    arrived a moment late releases nothing instead of releasing whatever
    hold came next (RT-13).
    """

    hold_id: int


class DrawRequest(BaseModel):
    """Body of ``POST /api/games/{id}/draw``."""

    position: int


class BidRequest(BaseModel):
    """Body of ``POST /api/games/{id}/bid``; ``amount`` of ``None`` is a pass."""

    amount: int | None = None


class ContractRequest(BaseModel):
    """Body of ``POST /api/games/{id}/contract``."""

    accept: bool


class TrumpRequest(BaseModel):
    """Body of ``POST /api/games/{id}/trump``."""

    suit: str


class PassRequest(BaseModel):
    """Body of ``POST /api/games/{id}/pass``."""

    cards: list[str]


class PlayRequest(BaseModel):
    """Body of ``POST /api/games/{id}/play``."""

    card: str
