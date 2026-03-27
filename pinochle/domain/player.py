# pinochle.domain.player
from dataclasses import dataclass, field
from enum import Enum


class PlayerType(Enum):
    """Supported player controller types."""

    HUMAN = "human"
    COMPUTER = "computer"


class Position(Enum):
    """Table positions in clockwise seat order."""

    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3


@dataclass
class Player:
    """A player registered in a game with seating and team metadata."""

    id: str
    name: str
    type: PlayerType
    position: Position
    team_id: str
