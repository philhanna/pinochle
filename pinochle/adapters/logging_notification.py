# pinochle.adapters.logging_notification
import logging

from pinochle.domain.game import CardsDealt, CardsPassed, GameEvent
from pinochle.ports.notification_port import NotificationPort


class LoggingNotification(NotificationPort):
    """``NotificationPort`` that writes an audit trail at ``INFO`` (NFR-9).

    Every delivery is logged with the game id and the recipient (a single
    seat for ``notify``, ``"*"`` for a ``broadcast``).  ``CardsDealt`` and
    ``CardsPassed`` carry a hand or a passed set of cards, so those two are
    redacted to a card count — the log must not itself become a way to leak
    a private hand.
    """

    def __init__(self, logger: logging.Logger | None = None):
        """Use ``logger``, or a module-level ``pinochle.events`` logger by default."""
        self._logger = logger or logging.getLogger("pinochle.events")

    def notify(self, player_id: str, event: GameEvent) -> None:
        """Log a single-player delivery."""
        self._log(event, recipient=player_id)

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Log a delivery to every player in the game."""
        self._log(event, recipient="*")

    def _log(self, event: GameEvent, *, recipient: str) -> None:
        """Write one ``event.published`` record, redacting private card lists."""
        self._logger.info(
            "event.published game_id=%s recipient=%s event=%s",
            event.game_id,
            recipient,
            self._describe(event),
        )

    @staticmethod
    def _describe(event: GameEvent) -> str:
        """Return a loggable description of ``event``, with hands redacted."""
        if isinstance(event, CardsDealt):
            return f"CardsDealt(player_id={event.player_id!r}, count={len(event.cards)})"
        if isinstance(event, CardsPassed):
            return (
                f"CardsPassed(from_player_id={event.from_player_id!r}, "
                f"to_player_id={event.to_player_id!r}, count={len(event.cards)})"
            )
        return repr(event)
