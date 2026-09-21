# tests.adapters.test_svg_card_image
import pytest

from pinochle.adapters.svg_card_image import SvgCardImage
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from tests.ports.test_card_image_port import run_contract


def test_contract():
    """Verify the image adapter satisfies the shared card-image contract."""
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
    """Each supported SVG face image should resolve to an existing asset."""
    images = SvgCardImage()
    path = images.get_image_path(Card(rank, suit), fmt="svg")
    from pathlib import Path
    assert Path(path).exists()


def test_png_path_exists():
    """PNG face lookups should resolve to an existing asset."""
    images = SvgCardImage()
    path = images.get_image_path(Card(Rank.ACE, Suit.SPADES), fmt="png")
    from pathlib import Path
    assert Path(path).exists()


def test_back_path_exists():
    """Both SVG and PNG back images should resolve to existing assets."""
    images = SvgCardImage()
    from pathlib import Path
    assert Path(images.get_back_path(fmt="svg")).exists()
    assert Path(images.get_back_path(fmt="png")).exists()


def test_get_back_path_serves_a_named_back():
    """UI-5: the caller may choose a back without knowing the adapter."""
    assert SvgCardImage().get_back_path(name="red").endswith("red.svg")


def test_get_back_path_defaults_when_no_name_is_given():
    """``None`` means the implementation's own default back."""
    images = SvgCardImage()
    assert images.get_back_path() == images.get_back_path(name=None)


def test_the_default_back_is_configurable_by_name():
    """The adapter is given a bare name and works out the path itself."""
    images = SvgCardImage(default_back="castle")
    assert images.get_back_path().endswith("castle.svg")
    assert images.get_back_path(fmt="png").endswith("castle.png")


def test_a_named_back_still_wins_over_the_configured_one():
    """A caller that asks for one back by name gets that one."""
    assert SvgCardImage(default_back="castle").get_back_path(name="red").endswith("red.svg")
