from unittest import TestCase

from pinochle import Card, Suit, Rank


class TestCardParse(TestCase):

    def test_parse_ten_of_diamonds(self):
        self.assertEqual(Card(Rank.TEN, Suit.DIAMONDS), Card.parse("10d"))

    def test_parse_ten_of_clubs(self):
        self.assertEqual(Card(Rank.TEN, Suit.CLUBS), Card.parse("10c"))

    def test_parse_ten_bad_suit(self):
        self.assertIsNone(Card.parse("10x"))

    def test_parse_ace_of_spades(self):
        self.assertEqual(Card(Rank.ACE, Suit.SPADES), Card.parse("as"))

    def test_parse_ace_bad_suit(self):
        self.assertIsNone(Card.parse("a"))

    def test_parse_empty_string(self):
        self.assertIsNone(Card.parse(""))
