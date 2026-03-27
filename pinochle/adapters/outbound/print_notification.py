# pinochle.adapters.outbound.print_notification
from pinochle.domain.game import GameEvent
from pinochle.ports.outbound.notification_port import NotificationPort


class PrintNotification(NotificationPort):
    """NotificationPort that logs events to stdout — useful for development."""

    def notify(self, player_id: str, event: GameEvent) -> None:
        print(f"[notify → {player_id}] {event}")

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        print(f"[broadcast → game {game_id}] {event}")
