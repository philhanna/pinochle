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
        dealer = Player("Dad")
        round = Round(self.players, dealer)
        limit = 10
        for player in round.player_iterator():
            print(player)
            limit -= 1
            if limit <= 0:
                break
        pass

