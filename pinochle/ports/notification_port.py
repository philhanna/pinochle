# pinochle.ports.notification_port
from abc import ABC, abstractmethod

from pinochle.domain.game import GameEvent


class NotificationPort(ABC):
    @abstractmethod
    def notify(self, player_id: str, event: GameEvent) -> None:
        """Push a game event to a specific player."""

    @abstractmethod
    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Push an event to all players in the game."""
