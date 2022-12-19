from pinochle import Card, Rank, Suit, CardParser


def test_constructor():
    rank: Rank = Rank.TEN
    suit: Suit = Suit.DIAMONDS
    card: Card = Card(rank, suit)
    card_name = str(card)
    assert "10 of Diamonds" == card_name


def test_parser():
    card: Card = CardParser.parse("10 of Diamonds")
    assert "10 of Diamonds" == str(card)


def test_parser_from_card_class():
    card: Card = Card.parse("9 of clubs")
    assert "Nine of Clubs" == str(card)


def test_repr():
    card: Card = Card.parse("9 of clubs")
    assert "Nine of Clubs" == repr(card)
