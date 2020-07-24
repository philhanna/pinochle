from unittest import TestCase

from pinochle import Hand, Deck, Suit


class TestHand(TestCase):

    def test_organized(self):
        deck = Deck()
        deck.shuffle()
        hand = Hand()
        for i, card in enumerate(deck.cards):
            if i % 4 == 0:
                hand.add(card)
        orgmap = hand.organized()
        for suitname, cardlist in orgmap.items():
            self.assertIn(suitname, [suit.value for suit in Suit])
            self.assertGreater(len(cardlist), 0)
            for card in cardlist:
                self.assertEqual(card.suit.value, suitname)
