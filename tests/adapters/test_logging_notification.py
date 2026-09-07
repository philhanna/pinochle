# tests.adapters.test_logging_notification
import logging

from pinochle.adapters.logging_notification import LoggingNotification
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.game import BidPlaced, CardsDealt, CardsPassed
from tests.ports.test_notification_port import run_contract


def test_contract():
    """Verify the logging notifier satisfies the shared notification contract."""
    run_contract(LoggingNotification())


def test_notify_and_broadcast_are_logged_at_info(caplog):
    """NFR-9: every delivery becomes one INFO-level audit record."""
    caplog.set_level(logging.INFO, logger="pinochle.events")
    notifier = LoggingNotification()

    notifier.notify("N", BidPlaced(game_id="g1", player_id="N", amount=250, current_high=250))
    notifier.broadcast("g1", BidPlaced(game_id="g1", player_id="N", amount=250, current_high=250))

    assert len(caplog.records) == 2
    assert all(r.levelno == logging.INFO for r in caplog.records)
    assert "g1" in caplog.records[0].message
    assert "N" in caplog.records[0].message
    assert "*" in caplog.records[1].message


def test_cards_dealt_is_redacted_to_a_count(caplog):
    """A dealt hand must never appear verbatim in the log (NFR-9)."""
    caplog.set_level(logging.INFO, logger="pinochle.events")
    notifier = LoggingNotification()
    hand = [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)]

    notifier.notify("N", CardsDealt(game_id="g1", player_id="N", cards=hand))

    message = caplog.records[0].message
    assert "count=2" in message
    assert "AS" not in message and str(Card(Rank.ACE, Suit.SPADES)) not in message


def test_cards_passed_is_redacted_to_a_count(caplog):
    """A partner pass must never reveal its cards in the log (NFR-9)."""
    caplog.set_level(logging.INFO, logger="pinochle.events")
    notifier = LoggingNotification()
    cards = [Card(Rank.ACE, Suit.SPADES)] * 4

    notifier.broadcast("g1", CardsPassed(
        game_id="g1", from_player_id="N", to_player_id="S", cards=cards,
    ))

    message = caplog.records[0].message
    assert "count=4" in message
