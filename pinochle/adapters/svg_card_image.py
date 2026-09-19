# pinochle.adapters.svg_card_image
from pathlib import Path

from pinochle.domain.cards.card import Card
from pinochle.ports.card_image_port import CardImagePort

_RESOURCES = (
    Path(__file__).parent.parent  # pinochle/
    / "card_images"
)

_DEFAULT_BACK = "blue"


class SvgCardImage(CardImagePort):
    """``CardImagePort`` that resolves image paths within the bundled card asset package.

    Assets live under ``pinochle/card_images/``, organized as:

    - ``fronts/`` — SVG face images named ``<suit>_<rank>.svg``.
    - ``fronts/png_96_dpi/`` — 96-dpi PNG equivalents.
    - ``backs/`` — SVG card-back images (default: ``blue.svg``).
    - ``backs/png_96_dpi/`` — PNG card-back equivalents.

    Raises ``FileNotFoundError`` if the requested asset does not exist on disk.
    """

    def get_image_path(self, card: Card, fmt: str = "svg") -> str:
        """Return the asset path for a specific card face image."""
        suit_name = card.suit.name.lower()      # e.g. "spades"
        rank_name = card.rank.rank_name.lower() # e.g. "ace", "10", "jack"
        filename = f"{suit_name}_{rank_name}.{fmt}"

        if fmt == "png":
            path = _RESOURCES / "fronts" / "png_96_dpi" / filename
        else:
            path = _RESOURCES / "fronts" / filename

        if not path.exists():
            raise FileNotFoundError(f"Card image not found: {path}")
        return str(path)

    def get_back_path(self, fmt: str = "svg", name: str | None = None) -> str:
        """Return the asset path for a named card back image."""
        filename = f"{name or _DEFAULT_BACK}.{fmt}"

        if fmt == "png":
            path = _RESOURCES / "backs" / "png_96_dpi" / filename
        else:
            path = _RESOURCES / "backs" / filename

        if not path.exists():
            raise FileNotFoundError(f"Card back image not found: {path}")
        return str(path)
