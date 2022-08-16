from unittest import TestCase

from pinochle.rank import Rank


class TestRank(TestCase):

    def test_name(self):
        self.assertEqual("Q", Rank.QUEEN.value)

    def test_str(self):
        self.assertEqual("Ace", str(Rank.ACE))

    def test_number_of_members(self):
        self.assertEqual(6, len(list(Rank)))

    def test_order(self):
        self.assertEqual(4, Rank.TEN.order())

    def test_greater_than(self):
        self.assertGreater(Rank.ACE, Rank.JACK)

    def test_less_than(self):
        self.assertLess(Rank.NINE, Rank.JACK)

    def test_equals(self):
        self.assertEqual(Rank.KING, Rank.KING)

    def test_greater_equals(self):
        self.assertGreaterEqual(Rank.ACE, Rank.ACE)
        self.assertGreaterEqual(Rank.ACE, Rank.JACK)

    def test_less_equals(self):
        self.assertLessEqual(Rank.TEN, Rank.TEN)
        self.assertLessEqual(Rank.KING, Rank.TEN)

    def test_not_equals(self):
        self.assertNotEqual(Rank.KING, Rank.JACK)

    def test_hash(self):
        expected = hash("KING")
        actual = hash(Rank.KING)
        self.assertEqual(expected, actual)
