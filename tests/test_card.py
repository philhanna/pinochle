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


