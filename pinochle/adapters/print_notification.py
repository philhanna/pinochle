# pinochle.adapters.print_notification
from pinochle.domain.game import GameEvent
from pinochle.ports.notification_port import NotificationPort


class PrintNotification(NotificationPort):
    """``NotificationPort`` implementation that writes events to stdout.

    Intended for local development, CLI runners, and integration tests where
    observing the raw event stream is more useful than a real delivery
    mechanism.  Each call formats the event as a labelled line:

    - ``notify`` prefixes with ``[notify → <player_id>]``.
    - ``broadcast`` prefixes with ``[broadcast → game <game_id>]``.
    """

    def notify(self, player_id: str, event: GameEvent) -> None:
        """Print a player-scoped event notification."""
        print(f"[notify → {player_id}] {event}")

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Print a game-wide event broadcast."""
        print(f"[broadcast → game {game_id}] {event}")
