# tests.ports.test_notification_port
"""Contract tests for NotificationPort."""
from pinochle.domain.game import DealerSelected
from pinochle.ports.notification_port import NotificationPort


def run_contract(notifier: NotificationPort) -> None:
    event = DealerSelected(game_id="g1", dealer_player_id="N")

    # Must not raise
    notifier.notify("N", event)
    notifier.broadcast("g1", event)
