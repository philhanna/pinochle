# pinochle.adapters.composite_notification
from pinochle.domain.game import GameEvent
from pinochle.ports.notification_port import NotificationPort


class CompositeNotification(NotificationPort):
    """``NotificationPort`` that tees every call to a list of other notifiers.

    Lets the service depend on exactly one port while still delivering each
    event to several destinations — the SSE hub, the audit log, and (once
    wired) the computer driver observing for its turn to act.
    """

    def __init__(self, notifiers: list[NotificationPort] | None = None):
        """Start with the given notifiers, or none."""
        self._notifiers: list[NotificationPort] = list(notifiers) if notifiers else []

    def append(self, notifier: NotificationPort) -> None:
        """Add another notifier to the end of the delivery list."""
        self._notifiers.append(notifier)

    def notify(self, player_id: str, event: GameEvent) -> None:
        """Forward a single-player delivery to every held notifier."""
        for notifier in self._notifiers:
            notifier.notify(player_id, event)

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Forward a broadcast to every held notifier."""
        for notifier in self._notifiers:
            notifier.broadcast(game_id, event)
