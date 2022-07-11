from unittest import TestCase

from pinochle import CardParser, Player, Card


class TestPlayer(TestCase):

    def test_choose_card(self):
        cards = [CardParser.parse(cardname) for cardname in ["As", "10d", "QS", "JD"]]
        player: Player = Player("Dad")
        card: Card = player.choose_card(cards)
        self.assertIn(card, cards)
