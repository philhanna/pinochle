from unittest import TestCase

from pinochle import Suit


class TestSuit(TestCase):

    def test_name(self):
        self.assertEqual("Hearts", Suit.HEARTS.value)
