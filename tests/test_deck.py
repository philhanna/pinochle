from unittest import TestCase

from pinochle import Deck


class TestDeck(TestCase):

    def test_cards(self):
        deck = Deck()
        self.assertEqual(48, len(deck.cards))

    def test_shuffle(self):
        deck = Deck()
        deck.shuffle()
        self.assertEqual(48, len(deck.cards))

