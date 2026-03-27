# pinochle.adapters.svg_card_image
from pathlib import Path

from pinochle.domain.cards.card import Card
from pinochle.ports.card_image_port import CardImagePort

_RESOURCES = (
    Path(__file__).parent.parent  # pinochle/
    / "cards" / "resources" / "svg_playing_cards"
)

_DEFAULT_BACK = "blue"


class SvgCardImage(CardImagePort):
    """CardImagePort that resolves paths into the bundled SVG/PNG assets."""

    def get_image_path(self, card: Card, fmt: str = "svg") -> str:
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

    def get_back_path(self, fmt: str = "svg", name: str = _DEFAULT_BACK) -> str:
        filename = f"{name}.{fmt}"

        if fmt == "png":
            path = _RESOURCES / "backs" / "png_96_dpi" / filename
        else:
            path = _RESOURCES / "backs" / filename

        if not path.exists():
            raise FileNotFoundError(f"Card back image not found: {path}")
        return str(path)
