from unittest import TestCase

from pinochle import Deck


class TestDeck(TestCase):

    def setUp(self):
        self.deck = Deck()

    def test_cards(self):
        deck = self.deck
        self.assertEqual(48, len(deck.cards))

    def test_shuffle(self):
        deck = self.deck
        deck.shuffle()
        self.assertIsNotNone(deck)
