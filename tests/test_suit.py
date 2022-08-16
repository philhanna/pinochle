from unittest import TestCase

from pinochle import Suit


class TestSuit(TestCase):

    def test_order_hearts(self):
        expected: str = "Hearts"
        actual: str = str(Suit.HEARTS)
        self.assertEqual(expected, actual)

    def test_order_clubs(self):
        expected: str = "Clubs"
        actual: str = str(Suit.CLUBS)
        self.assertEqual(expected, actual)

    def test_order_diamonds(self):
        expected: str = "Diamonds"
        actual: str = str(Suit.DIAMONDS)
        self.assertEqual(expected, actual)

    def test_order_spades(self):
        expected: str = "Spades"
        actual: str = str(Suit.SPADES)
        self.assertEqual(expected, actual)
