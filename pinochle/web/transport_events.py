# pinochle.web.transport_events
from dataclasses import dataclass

# design.md §14.3: RT-12 requires the table be told a seat is gone, or that
# the administrator ended the game, but the domain knows nothing about
# connections. These three are published by the hub and the admin router
# rather than by Game, so they live here rather than in domain.game.


@dataclass
class SeatLost:
    """Published when a seat's last open stream closes."""

    game_id: str
    player_id: str


@dataclass
class SeatRejoined:
    """Published when a stream opens for a seat that previously had none."""

    game_id: str
    player_id: str


@dataclass
class GameAbandoned:
    """Published when the administrator ends a game that cannot continue."""

    game_id: str
    reason: str
