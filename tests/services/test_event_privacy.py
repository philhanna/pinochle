# tests.services.test_event_privacy
from pinochle.adapters.immediate_scheduler import ImmediateScheduler
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.game import (
    BidPlaced,
    CardsDealt,
    CardsPassed,
    Game,
    GameEvent,
    MeldExposed,
)
from pinochle.ports.notification_port import NotificationPort
from pinochle.services.game_service import GameService


class RecordingNotification(NotificationPort):
    """``NotificationPort`` double that records every delivery for inspection."""

    def __init__(self):
        """Start with empty delivery logs."""
        self.notified: list[tuple[str, GameEvent]] = []
        self.broadcast_events: list[GameEvent] = []

    def notify(self, player_id: str, event: GameEvent) -> None:
        """Record a single-player delivery."""
        self.notified.append((player_id, event))

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Record a delivery to every player in the game."""
        self.broadcast_events.append(event)


def make_service() -> tuple[GameService, RecordingNotification]:
    """Return a service wired to a recording notifier."""
    notifier = RecordingNotification()
    service = GameService(InMemoryGameState(), notifier, ImmediateScheduler())
    return service, notifier


def dispatch(service: GameService, *events: GameEvent) -> Game:
    """Emit ``events`` on a fresh game and run them through the dispatcher."""
    game = Game("g1")
    for event in events:
        game.emit(event)
    service._dispatch(game)
    return game


def test_dealt_hand_goes_only_to_its_owner():
    """A dealt hand must never be broadcast to the whole table."""
    service, notifier = make_service()
    dispatch(service, CardsDealt(
        game_id="g1",
        player_id="N",
        cards=[Card(Rank.ACE, Suit.SPADES)],
    ))
    assert notifier.broadcast_events == []
    assert [pid for pid, _ in notifier.notified] == ["N"]


def test_pass_goes_only_to_the_two_partners():
    """Passed cards are visible to the bidding team and to nobody else."""
    service, notifier = make_service()
    dispatch(service, CardsPassed(
        game_id="g1",
        from_player_id="E",
        to_player_id="W",
        cards=[Card(Rank.KING, Suit.HEARTS)],
    ))
    assert notifier.broadcast_events == []
    assert sorted(pid for pid, _ in notifier.notified) == ["E", "W"]


def test_public_events_are_broadcast():
    """Bids and exposed meld were public at the table and stay public here."""
    service, notifier = make_service()
    dispatch(
        service,
        BidPlaced(game_id="g1", player_id="E", amount=250),
        MeldExposed(game_id="g1", player_id="E", units=[], total=0),
    )
    assert notifier.notified == []
    assert len(notifier.broadcast_events) == 2


def test_dispatch_drains_the_event_queue():
    """Dispatched events are cleared, so a later dispatch re-sends nothing."""
    service, notifier = make_service()
    game = dispatch(service, BidPlaced(game_id="g1", player_id="E", amount=250))
    notifier.broadcast_events.clear()
    service._dispatch(game)
    assert notifier.broadcast_events == []
