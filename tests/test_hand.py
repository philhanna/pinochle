from unittest import TestCase

from pinochle import Hand, Deck


class TestHand(TestCase):

    def test_organize(self):
        deck = Deck()
        deck.shuffle()
        hand = Hand()
        for i, card in enumerate(deck.cards):
            if i % 4 == 0:
                hand.add(card)
        suitmap = hand.organized()
        for k, v in suitmap.items():
            line = k + ":" + " ".join([card.rank.value for card in v])
            print(line)
