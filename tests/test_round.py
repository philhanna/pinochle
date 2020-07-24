from unittest import TestCase


from pinochle import Round, Player, Team


class TestRound(TestCase):

    def setUp(self):
        self.players = players = [
            Player("John"),
            Player("Ellie"),
            Player("Dad"),
            Player("Mom"),
        ]
        pass

    def test_player_iterator(self):
        john, ellie, dad, mom = self.players
        dealer = dad
        actual = []
        for player in Round(self.players, dealer).player_iterator():
            actual.append(player)
            if len(actual) == 6:
                break
        expected = [mom, john, ellie, dad, mom, john]
        self.assertListEqual(expected, actual)
