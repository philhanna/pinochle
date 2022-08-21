from unittest import TestCase

from pinochle import Card, Rank, Suit, CardParser


class TestCard(TestCase):

    def test_constructor(self):
        rank: Rank = Rank.TEN
        suit: Suit = Suit.DIAMONDS
        card: Card = Card(rank, suit)
        card_name = str(card)
        self.assertEqual("10 of Diamonds", card_name)

    def test_parser(self):
        card: Card = CardParser.parse("10 of Diamonds")
        self.assertEqual("10 of Diamonds", str(card))

    def test_parser_from_card_class(self):
        card: Card = Card.parse("9 of clubs")
        self.assertEqual("Nine of Clubs", str(card))

    def test_repr(self):
        card: Card = Card.parse("9 of clubs")
        self.assertEqual("Nine of Clubs", repr(card))
