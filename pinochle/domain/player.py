# pinochle.domain.player
from dataclasses import dataclass
from enum import Enum

from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID


class PlayerType(Enum):
    """Distinguishes how a player's decisions are made.

    ``HUMAN`` players submit actions through a delivery mechanism (API, CLI,
    or UI).  ``COMPUTER`` players are driven autonomously by a strategy such
    as ``ComputerPlayerStrategy``.
    """

    HUMAN = "human"
    COMPUTER = "computer"


class Position(Enum):
    """The four table seats in clockwise order, starting from North.

    The integer value of each member encodes the seat index and is used to
    derive turn order and partnership pairing: seats 0 (NORTH) and 2 (SOUTH)
    form one team, while seats 1 (EAST) and 3 (WEST) form the other.
    """

    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

    @property
    def team_id(self) -> str:
        """Return the partnership this seat belongs to."""
        return NS_TEAM_ID if self in (Position.NORTH, Position.SOUTH) else EW_TEAM_ID


@dataclass
class Player:
    """A player registered in a game, carrying seating and team metadata.

    Attributes:
        id: Stable unique identifier used throughout the system to reference
            this player in events, hands, and bids.
        name: Human-readable display name.
        type: Whether the player is controlled by a human or the computer AI.
        position: The table seat occupied by this player, which determines
            turn order and partnership pairing.

    The partnership is not stored: it follows from ``position``, so a player
    seated North on the East/West team cannot be represented at all.
    """

    id: str
    name: str
    type: PlayerType
    position: Position

    @property
    def team_id(self) -> str:
        """Return the partnership implied by this player's seat."""
        return self.position.team_id
