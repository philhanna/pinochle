from unittest import TestCase

from pinochle.rank import Rank


class TestRank(TestCase):

    def test_name(self):
        self.assertEqual("Q", Rank.QUEEN.value)

    def test_fullname(self):
        self.assertEqual("Ace", Rank.ACE.fullname())

    def test_number_of_members(self):
        self.assertEqual(6, len(list(Rank)))

    def test_order(self):
        self.assertEqual(4, Rank.TEN.order())

    def test_greater_than(self):
        self.assertGreater(Rank.ACE, Rank.JACK)
