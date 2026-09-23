# pinochle.adapters.in_memory_seat_tokens
import secrets
from typing import Callable

from pinochle.ports.seat_token_port import SeatTokenPort


class InMemorySeatTokens(SeatTokenPort):
    """``SeatTokenPort`` backed by a plain in-memory ``dict``.

    Tokens are opaque strings produced by an injectable factory, which
    defaults to ``secrets.token_urlsafe(32)`` for production use; tests
    inject a deterministic factory instead.  State is lost when the process
    exits, matching NFR-8's in-memory-only game state.
    """

    def __init__(self, token_factory: Callable[[], str] | None = None):
        """Store tokens per game, using ``token_factory`` to mint new ones."""
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._tokens: dict[str, dict[str, str]] = {}

    def mint(self, game_id: str, player_id: str) -> str:
        """Create, store, and return a fresh token for ``player_id`` in ``game_id``."""
        token = self._token_factory()
        self._tokens.setdefault(game_id, {})[token] = player_id
        return token

    def resolve(self, game_id: str, token: str) -> str | None:
        """Return the player id ``token`` seats in ``game_id``, or ``None``."""
        return self._tokens.get(game_id, {}).get(token)

    def revoke_seat(self, game_id: str, player_id: str) -> None:
        """Discard every token seating ``player_id`` in ``game_id`` (RT-12a).

        Every one of them: a seat may have been issued more than one token
        over a long evening, and unlinking a player that left one of them
        still working would leave the seat open to whoever holds it.
        """
        issued = self._tokens.get(game_id)
        if issued is None:
            return
        for token in [t for t, seated in issued.items() if seated == player_id]:
            del issued[token]

    def revoke_game(self, game_id: str) -> None:
        """Discard every token issued for ``game_id``."""
        self._tokens.pop(game_id, None)
