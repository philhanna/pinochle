from unittest import TestCase

from pinochle import Card, Suit, Rank


class TestCardParse(TestCase):

    def test_parse_ten(self):
        s = "10clubsasdfasdf"
        expected = Card(Rank.TEN, Suit.CLUBS)
        actual = Card.parse(s)
        self.assertEqual(expected, actual)
