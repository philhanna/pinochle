from unittest import TestCase

from pinochle import Player
from pinochle.players import Players


class TestPlayers(TestCase):

    def setUp(self):
        self.players = Players(
            Player("John"),
            Player("Ellie"),
            Player("Dad"),
            Player("Mom"))

    def test_next_player(self):
        players = self.players
        john, ellie, dad, mom = players.players
        player = None

        player = players.next_player(player)
        self.assertEqual(john, player)

        player = players.next_player(player)
        self.assertEqual(ellie, player)

        player = players.next_player(player)
        self.assertEqual(dad, player)

        player = players.next_player(player)
        self.assertEqual(mom, player)

        player = players.next_player(player)
        self.assertEqual(john, player)
