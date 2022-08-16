from unittest import TestCase

from pinochle import Suit


class TestSuit(TestCase):

    def test_order_hearts(self):
        expected: int = 0
        actual: int = Suit.HEARTS.order()
        self.assertEqual(expected, actual)

    def test_order_clubs(self):
        expected: int = 1
        actual: int = Suit.CLUBS.order()
        self.assertEqual(expected, actual)

    def test_order_diamonds(self):
        expected: int = 2
        actual: int = Suit.DIAMONDS.order()
        self.assertEqual(expected, actual)

    def test_order_spades(self):
        expected: int = 3
        actual: int = Suit.SPADES.order()
        self.assertEqual(expected, actual)
