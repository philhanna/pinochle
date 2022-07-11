from unittest import TestCase

from pinochle import Card, Rank, Suit, CardParser


class TestCard(TestCase):

    def test_str(self):
        card = Card(Rank.QUEEN, Suit.SPADES)
        expected = "Queen of Spades"
        actual = str(card)
        self.assertEqual(expected, actual)

    def test_named_card(self):
        card = CardParser.parse("AD")
        expected = "Ace of Diamonds"
        actual = str(card)
        self.assertEqual(expected, actual)
