# pinochle.adapters.print_notification
from pinochle.domain.game import GameEvent
from pinochle.ports.notification_port import NotificationPort


class PrintNotification(NotificationPort):
    """NotificationPort that logs events to stdout — useful for development."""

    def notify(self, player_id: str, event: GameEvent) -> None:
        """Print a player-scoped event notification."""
        print(f"[notify → {player_id}] {event}")

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Print a game-wide event broadcast."""
        print(f"[broadcast → game {game_id}] {event}")
