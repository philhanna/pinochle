# pinochle.ports.card_image_port
from abc import ABC, abstractmethod

from pinochle.domain.cards.card import Card


class CardImagePort(ABC):
    """Secondary port for resolving card face and back image asset paths.

    Decouples the application from the physical location and format of card
    artwork.  Implementations may resolve bundled SVG/PNG files
    (``SvgCardImage``), fetch remote URLs, or return placeholder paths for
    testing.
    """

    @abstractmethod
    def get_image_path(self, card: Card, fmt: str = "svg") -> str:
        """Return a filesystem path for the card face image.

        Args:
            card: The card to look up.
            fmt: File format — "svg" or "png".
        """

    @abstractmethod
    def get_back_path(self, fmt: str = "svg", name: str | None = None) -> str:
        """Return a filesystem path for a card back image.

        Args:
            fmt: File format — "svg" or "png".
            name: Which back to use, or ``None`` for the implementation's
                own default.  Named here rather than left to the concrete
                adapter because a caller that serves a chosen back (UI-5)
                would otherwise have to know which adapter it holds.
        """
