import pytest

from pinochle import Player, CardParser, Card, Rank, Suit


@pytest.fixture
def player():
    return Player("John Doe")


def test_init(player):
    player1 = player
    player2 = Player("John Doe")
    assert player1.name == player2.name


def test_add_card_to_hand(player):
    player = player
    player.add_card_to_hand(CardParser.parse("Queen of Spades"))
    player.add_card_to_hand(CardParser.parse("Jack of Diamonds"))
    actual: list[Card] = player.cards
    expected: list[Card] = [Card(Rank.QUEEN, Suit.SPADES), Card(Rank.JACK, Suit.DIAMONDS)]
    assert actual == expected


def test_partner(player):
    cat = Player("Catherine Wood")
    player.partner = cat
    expected = cat
    actual = player.partner
    assert actual == expected


def test_repr(player):
    expected = 'Player("John Doe")'
    actual = repr(player)
    assert actual == expected


def test_str(player):
    expected = "John Doe"
    actual = str(player)
    assert actual == expected


def test_eq(player):
    player1 = player
    player2 = Player("John Doe")
    assert str(player1) == str(player2)
    assert player1 is player1
    assert player2 is player2
    assert player1 is not player2
