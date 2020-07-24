from unittest import TestCase

from pinochle import Player, Game


class TestGame(TestCase):

    def setUp(self):
        self.players = [
            Player("John"),
            Player("Ellie"),
            Player("Dad"),
            Player("Mom")]

    def test_choose_dealer(self):
        game = Game(self.players)
        dealer = game.choose_dealer()
        self.assertIn(dealer, self.players)
