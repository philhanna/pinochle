# pinochle.ports.outbound.card_image_port
from abc import ABC, abstractmethod

from pinochle.domain.cards.card import Card


class CardImagePort(ABC):
    @abstractmethod
    def get_image_path(self, card: Card, fmt: str = "svg") -> str:
        """Return a filesystem path for the card face image.

        Args:
            card: The card to look up.
            fmt: File format — "svg" or "png".
        """

    @abstractmethod
    def get_back_path(self, fmt: str = "svg") -> str:
        """Return a filesystem path for the card back image."""
