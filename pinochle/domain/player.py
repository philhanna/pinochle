# pinochle.domain.player
from dataclasses import dataclass, field
from enum import Enum


class PlayerType(Enum):
    HUMAN = "human"
    COMPUTER = "computer"


class Position(Enum):
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3


@dataclass
class Player:
    id: str
    name: str
    type: PlayerType
    position: Position
    team_id: str
