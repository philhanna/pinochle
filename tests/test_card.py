from unittest import TestCase

from pinochle import Card, Rank, Suit


class TestCard(TestCase):

    def test_str(self):
        card = Card(Rank.QUEEN, Suit.SPADES)
        expected = "Queen of Spades"
        actual = str(card)
        self.assertEqual(expected, actual)
