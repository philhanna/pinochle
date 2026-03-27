# pinochle.ports.notification_port
from abc import ABC, abstractmethod

from pinochle.domain.game import GameEvent


class NotificationPort(ABC):
    """Secondary port for delivering domain events to players.

    Implementations may write to stdout (for development), push over
    WebSockets, send emails, or use any other channel.  The core depends
    only on this interface, keeping delivery technology swappable.

    ``notify`` targets a single player; ``broadcast`` sends to all
    participants in a game and is used for public events such as trick
    completions and scoring.
    """

    @abstractmethod
    def notify(self, player_id: str, event: GameEvent) -> None:
        """Push a game event to a specific player."""

    @abstractmethod
    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Push an event to all players in the game."""
