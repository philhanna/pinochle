from unittest import TestCase

from pinochle import Round, Player


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

    def test_bad_dealer(self):
        dealer = Player("somebody else")
        with self.assertRaises(ValueError):
            Round(self.players, dealer).deal()

    def test_deal(self):
        john, ellie, dad, mom = self.players
        dealer = john
        round = Round(self.players, dealer)
        round.deal()
        for player in self.players:
            self.assertEqual(12, len(player.hand.cards))
