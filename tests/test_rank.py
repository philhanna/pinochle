import pytest

from pinochle.rank import Rank


@pytest.mark.parametrize("value", [
    4 == Rank.TEN.order(),
    6 == len(list(Rank)),
    "Ace" == str(Rank.ACE),
    hash("KING") == hash(Rank.KING),
    "Q" == Rank.QUEEN.value,
    Rank.KING == Rank.KING,
    Rank.ACE >= Rank.ACE,
    Rank.ACE >= Rank.JACK,
    Rank.ACE > Rank.JACK,
    Rank.KING <= Rank.TEN,
    Rank.TEN <= Rank.TEN,
    Rank.NINE < Rank.JACK,
    Rank.KING != Rank.JACK,
])
def test_value(value):
    assert value
