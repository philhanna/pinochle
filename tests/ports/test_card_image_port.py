# tests.ports.test_card_image_port
"""Contract tests for CardImagePort."""
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.ports.card_image_port import CardImagePort


def run_contract(images: CardImagePort) -> None:
    """Assert the card-image adapter returns usable paths for required assets."""
    card = Card(Rank.ACE, Suit.SPADES)

    svg_path = images.get_image_path(card, fmt="svg")
    assert isinstance(svg_path, str) and len(svg_path) > 0

    png_path = images.get_image_path(card, fmt="png")
    assert isinstance(png_path, str) and len(png_path) > 0

    back_svg = images.get_back_path(fmt="svg")
    assert isinstance(back_svg, str) and len(back_svg) > 0

    # An unnamed back must resolve to the implementation's own default, so a
    # caller can serve a back without knowing which adapter it holds (UI-5).
    assert images.get_back_path(fmt="svg", name=None) == back_svg
