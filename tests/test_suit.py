from unittest import TestCase

from pinochle.suit import Suit


class TestSuit(TestCase):

    def test_string_value(self):
        self.assertEqual("Diamonds", Suit.DIAMONDS.value)

    def test_number_of_members(self):
        self.assertEqual(4, len(list(Suit)))
