# pinochle.adapters.sse_notification
import asyncio
from collections import deque

from pinochle.domain.game import GameEvent
from pinochle.ports.notification_port import NotificationPort

# Put on a queue in place of an event to end that stream from this side
# (RT-12a).  A queue otherwise only ever carries ``(seq, event)`` pairs, so a
# reader tells the two apart by identity and needs no wrapper type.
STREAM_CLOSED = object()


class SseNotification(NotificationPort):
    """``NotificationPort`` that fans events out to per-seat SSE subscriber queues.

    Does no serialization — a queue receives ``(seq, event)`` pairs, and
    turning one into a wire frame is ``event_encoder.py``'s job.  ``seq`` is a
    per-game monotonic sequence number assigned once per dispatched event,
    before fan-out, so it reflects one shared order across every seat and the
    admin, regardless of who reads it first.  A seat may hold several queues at
    once (FR-10c, e.g. two open tabs); all of them receive every event
    addressed to that seat.  The admin's own queues receive exactly the
    broadcasts (§6.3), which is what makes it structurally impossible for the
    admin console to see a hand.

    It also keeps what it dispatched, so a seat whose connection drops can be
    handed the frames it missed and carry on (RT-5a).  The history records who
    each event was addressed to, and ``history_since`` filters by that, so a
    resumed stream can no more see another seat's hand than a live one can.
    """

    def __init__(self, queue_maxsize: int = 256, history_maxlen: int = 20000):
        """Start with no subscribers.

        ``queue_maxsize`` bounds each new queue; ``history_maxlen`` bounds the
        replay buffer per game, which is what a dropped connection resumes
        from.  A whole game to 2000 points runs to a few thousand events, so
        the default holds one several times over.  The entries are references
        to events that exist anyway, and the cost of keeping too few of them
        is a player who cannot get back to the table.
        """
        self._queue_maxsize = queue_maxsize
        self._history_maxlen = history_maxlen
        self._seats: dict[str, dict[str, set[asyncio.Queue]]] = {}
        self._admins: dict[str, set[asyncio.Queue]] = {}
        self._seq: dict[str, int] = {}
        # Per game: the events dispatched, each with the seat it was private
        # to (None for a broadcast), oldest first.
        self._history: dict[str, deque[tuple[int, str | None, GameEvent]]] = {}

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

    def close_seat(self, game_id: str, player_id: str) -> int:
        """End every stream ``player_id`` holds open, and say how many (RT-12a).

        Unsubscribing on its own would not do it.  A stream is held open by a
        generator waiting on its queue, and one that is never told to stop
        waits forever — it would go on holding the seat open for a player the
        administrator has just unlinked, and go on being resumable with the
        credential that opened it.  So each queue is handed the sentinel that
        ends its generator, which then unsubscribes itself by the ordinary
        route and lets the table hear that the seat is gone.

        A queue with no room left is one whose client stopped reading long
        ago; the oldest frame on it is dropped to make room, since a stream
        being closed has no use for it.
        """
        queues = self._seats.get(game_id, {}).pop(player_id, set())
        for queue in queues:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(STREAM_CLOSED)
        return len(queues)

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
        self._remember(event.game_id, seq, player_id, event)
        self._deliver(seats.get(player_id, set()), seq, event)

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Deliver ``event`` to every seat's queues, plus every admin queue."""
        seq = self._next_seq(game_id)
        self._remember(game_id, seq, None, event)
        for queues in self._seats.get(game_id, {}).values():
            self._deliver(queues, seq, event)
        self._deliver(self._admins.get(game_id, set()), seq, event)

    def history_since(
        self, game_id: str, player_id: str, after_seq: int,
    ) -> tuple[list[tuple[int, GameEvent]], bool]:
        """Return what ``player_id`` missed after ``after_seq``, and whether it is whole.

        The events are the ones that seat was entitled to at the time — its
        own private frames and the table's broadcasts, never another seat's —
        in their original order, so a client can fold them in exactly as if
        they had arrived live (RT-5a).

        The flag is False when the buffer no longer reaches back to
        ``after_seq``: the caller has to say so rather than hand over a
        history with a hole in it, since a client folding one would be
        quietly wrong about the game rather than visibly behind.  It says
        nothing about how much there is to replay — a seat that missed
        nothing and one that missed the whole game are both whole, as long as
        what it missed is all still here.
        """
        entries = self._history.get(game_id)
        if entries is None:
            # Nothing dispatched yet: a stream from 0 is vacuously whole, and
            # one from further on is asking about a game this process lost.
            return [], after_seq == 0
        whole = not entries or entries[0][0] <= after_seq + 1
        missed = [
            (seq, event)
            for seq, recipient, event in entries
            if seq > after_seq and recipient in (None, player_id)
        ]
        return missed, whole

    def _remember(
        self, game_id: str, seq: int, recipient: str | None, event: GameEvent,
    ) -> None:
        """Keep ``event`` for replay, oldest dropping out once the buffer is full."""
        entries = self._history.get(game_id)
        if entries is None:
            entries = deque(maxlen=self._history_maxlen)
            self._history[game_id] = entries
        entries.append((seq, recipient, event))

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
