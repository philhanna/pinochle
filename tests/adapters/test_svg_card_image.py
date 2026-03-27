# tests.adapters.test_svg_card_image
import pytest

from pinochle.adapters.svg_card_image import SvgCardImage
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from tests.ports.test_card_image_port import run_contract


def test_contract():
    run_contract(SvgCardImage())


@pytest.mark.parametrize("rank,suit", [
    (Rank.ACE, Suit.SPADES),
    (Rank.TEN, Suit.HEARTS),
    (Rank.KING, Suit.DIAMONDS),
    (Rank.QUEEN, Suit.CLUBS),
    (Rank.JACK, Suit.SPADES),
    (Rank.NINE, Suit.HEARTS),
])
def test_svg_path_exists(rank, suit):
    images = SvgCardImage()
    path = images.get_image_path(Card(rank, suit), fmt="svg")
    from pathlib import Path
    assert Path(path).exists()


def test_png_path_exists():
    images = SvgCardImage()
    path = images.get_image_path(Card(Rank.ACE, Suit.SPADES), fmt="png")
    from pathlib import Path
    assert Path(path).exists()


def test_back_path_exists():
    images = SvgCardImage()
    from pathlib import Path
    assert Path(images.get_back_path(fmt="svg")).exists()
    assert Path(images.get_back_path(fmt="png")).exists()
