# pinochle.adapters.sse_notification
import asyncio

from pinochle.domain.game import GameEvent
from pinochle.ports.notification_port import NotificationPort


class SseNotification(NotificationPort):
    """``NotificationPort`` that fans events out to per-seat SSE subscriber queues.

    Holds no history and does no serialization — a queue receives
    ``(seq, event)`` pairs, and turning one into a wire frame is
    ``event_encoder.py``'s job.  ``seq`` is a per-game monotonic sequence
    number assigned once per dispatched event, before fan-out, so it reflects
    one shared order across every seat and the admin, regardless of who
    reads it first.  A seat may hold several queues at once (FR-10c, e.g. two
    open tabs); all of them receive every event addressed to that seat.  The
    admin's own queues receive exactly the broadcasts (§6.3), which is what
    makes it structurally impossible for the admin console to see a hand.
    """

    def __init__(self, queue_maxsize: int = 256):
        """Start with no subscribers; ``queue_maxsize`` bounds each new queue."""
        self._queue_maxsize = queue_maxsize
        self._seats: dict[str, dict[str, set[asyncio.Queue]]] = {}
        self._admins: dict[str, set[asyncio.Queue]] = {}
        self._seq: dict[str, int] = {}

    def subscribe(self, game_id: str, player_id: str) -> asyncio.Queue:
        """Open and register a new queue for ``player_id`` in ``game_id``."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_maxsize)
        self._seats.setdefault(game_id, {}).setdefault(player_id, set()).add(queue)
        return queue

    def unsubscribe(self, game_id: str, player_id: str, queue: asyncio.Queue) -> None:
        """Remove ``queue`` from ``player_id``'s subscribers, if still present."""
        seats = self._seats.get(game_id, {})
        seats.get(player_id, set()).discard(queue)

    def subscribe_admin(self, game_id: str) -> asyncio.Queue:
        """Open and register a new admin queue for ``game_id``."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_maxsize)
        self._admins.setdefault(game_id, set()).add(queue)
        return queue

    def unsubscribe_admin(self, game_id: str, queue: asyncio.Queue) -> None:
        """Remove ``queue`` from the admin subscribers, if still present."""
        self._admins.get(game_id, set()).discard(queue)

    def seats_connected(self, game_id: str) -> set[str]:
        """Return the seats that currently have at least one open queue."""
        return {
            player_id
            for player_id, queues in self._seats.get(game_id, {}).items()
            if queues
        }

    def notify(self, player_id: str, event: GameEvent) -> None:
        """Deliver ``event`` to every queue belonging to ``player_id``."""
        seats = self._seats.get(event.game_id, {})
        seq = self._next_seq(event.game_id)
        self._deliver(seats.get(player_id, set()), seq, event)

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Deliver ``event`` to every seat's queues, plus every admin queue."""
        seq = self._next_seq(game_id)
        for queues in self._seats.get(game_id, {}).values():
            self._deliver(queues, seq, event)
        self._deliver(self._admins.get(game_id, set()), seq, event)

    def _next_seq(self, game_id: str) -> int:
        """Return the next per-game monotonic sequence number, starting at 1.

        Assigned once per dispatched event — whether it fans out to one seat
        via ``notify`` or the whole table via ``broadcast`` — so ``id:``
        reflects one shared, gapless order for everything published in a
        game (§6.4).
        """
        self._seq[game_id] = self._seq.get(game_id, 0) + 1
        return self._seq[game_id]

    @staticmethod
    def _deliver(queues: set[asyncio.Queue], seq: int, event: GameEvent) -> None:
        """Put ``(seq, event)`` on each of ``queues``, dropping any that are full.

        A full queue means that subscriber is hopelessly behind (§6.8); it is
        removed here so the game keeps flowing to everyone else.  Telling the
        dropped client itself (a final ``stream_broken`` frame) is the
        stream router's job.
        """
        dropped = set()
        for queue in queues:
            try:
                queue.put_nowait((seq, event))
            except asyncio.QueueFull:
                dropped.add(queue)
        queues -= dropped
