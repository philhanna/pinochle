from unittest import TestCase

from pinochle import Deck


class TestDeck(TestCase):

    def test_cards(self):
        deck = Deck()
        for card in deck.cards:
            print(card)
