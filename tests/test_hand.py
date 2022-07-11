from unittest import TestCase

from pinochle import Hand, Deck, Suit, CardParser


class TestHand(TestCase):

    def setUp(self):
        deck = Deck()
        deck.shuffle()
        hand = Hand()
        for i, card in enumerate(deck.cards):
            if i % 4 == 0:
                hand.add(card)
        self.hand = hand

    def test_organized(self):
        orgmap = self.hand.organized()
        for suitname, cardlist in orgmap.items():
            self.assertIn(suitname, [suit.value for suit in Suit])
            self.assertGreater(len(cardlist), 0)
            for card in cardlist:
                self.assertEqual(card.suit.value, suitname)

    def test_str(self):
        actual = str(self.hand)
        # All we can do here is check that at least one suit name
        # is mentioned in the string
        self.assertTrue(any([suit.value in actual for suit in Suit]))

    def test_with_initial_cards(self):
        cards = [CardParser.parse(cardname) for cardname in ["As", "10d", "QS", "JD"]]
        hand = Hand(cards)
        self.assertEqual(4, len(hand.cards))
