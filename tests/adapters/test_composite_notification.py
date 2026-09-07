# tests.adapters.test_composite_notification
from pinochle.adapters.composite_notification import CompositeNotification
from pinochle.domain.game import DealerSelected
from pinochle.ports.notification_port import NotificationPort
from tests.ports.test_notification_port import run_contract


class _RecordingNotifier(NotificationPort):
    """Minimal ``NotificationPort`` double that remembers what it received."""

    def __init__(self):
        self.notified = []
        self.broadcast_events = []

    def notify(self, player_id, event):
        self.notified.append((player_id, event))

    def broadcast(self, game_id, event):
        self.broadcast_events.append((game_id, event))


def test_contract():
    """An empty composite still satisfies the shared notification contract."""
    run_contract(CompositeNotification())


def test_notify_is_forwarded_to_every_held_notifier():
    """Every notifier in the list should receive the same private event."""
    a, b = _RecordingNotifier(), _RecordingNotifier()
    composite = CompositeNotification([a, b])
    event = DealerSelected(game_id="g1", dealer_player_id="N")

    composite.notify("N", event)

    assert a.notified == [("N", event)]
    assert b.notified == [("N", event)]


def test_broadcast_is_forwarded_to_every_held_notifier():
    """Every notifier in the list should receive the same broadcast event."""
    a, b = _RecordingNotifier(), _RecordingNotifier()
    composite = CompositeNotification([a, b])
    event = DealerSelected(game_id="g1", dealer_player_id="N")

    composite.broadcast("g1", event)

    assert a.broadcast_events == [("g1", event)]
    assert b.broadcast_events == [("g1", event)]


def test_append_adds_a_notifier_after_construction():
    """The computer driver is appended once it exists, per design.md §4.6."""
    a = _RecordingNotifier()
    composite = CompositeNotification([a])
    b = _RecordingNotifier()
    composite.append(b)

    event = DealerSelected(game_id="g1", dealer_player_id="N")
    composite.broadcast("g1", event)

    assert a.broadcast_events == [("g1", event)]
    assert b.broadcast_events == [("g1", event)]
