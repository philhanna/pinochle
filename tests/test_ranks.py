import pytest

from cards import Rank

@pytest.mark.parametrize("rank1, rank2, expected", [
    (Rank.NINE, Rank.QUEEN, False),
    (Rank.TEN, Rank.JACK, True),
    (Rank.KING, Rank.KING, False),
    (Rank.QUEEN, Rank.NINE, True),
])
def test_greater_than(rank1, rank2, expected):
    actual = rank1.value > rank2.value
    assert actual == expected