from unittest import TestCase

from pinochle import CardParser


class TestPlayer(TestCase):

    def test_choose_card(self):
        cards = [CardParser.parse(cardname) for cardname in ["As", "10d", "QS", "JD"]]
        print(cards)
