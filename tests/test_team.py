from unittest import TestCase

from pinochle import Player, Team


class TestTeam(TestCase):

    def test_players(self):
        team = Team(Player("John"), Player("Dad"))
        self.assertEqual("John and Dad", str(team))
        p1, p2 = team.players
        self.assertEqual(p1, Player("John"))
        self.assertEqual(p2, Player("Dad"))
