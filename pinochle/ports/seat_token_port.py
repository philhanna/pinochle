# pinochle.ports.seat_token_port
from abc import ABC, abstractmethod


class SeatTokenPort(ABC):
    """Secondary port for minting and resolving the per-seat credentials of FR-10.

    A seat token is the sole credential that authorises a player's requests
    for one game (FR-10a); implementations must make it unguessable in
    production while staying deterministic under test.
    """

    @abstractmethod
    def mint(self, game_id: str, player_id: str) -> str:
        """Create and store an unguessable token for one seat."""

    @abstractmethod
    def resolve(self, game_id: str, token: str) -> str | None:
        """Return the player id the token seats, or None if it is not valid."""

    @abstractmethod
    def revoke_seat(self, game_id: str, player_id: str) -> None:
        """Forget every token issued for one seat, unlinking its player (RT-12a)."""

    @abstractmethod
    def revoke_game(self, game_id: str) -> None:
        """Forget every token issued for a finished or abandoned game."""
