from unittest import TestCase

from pinochle import Bidding, Player, PASS


class TestBidding(TestCase):

    def setUp(self):
        self.players = [
            Player("John"),
            Player("Ellie"),
            Player("Dad"),
            Player("Mom"),
        ]

    def test_player_to_dealers_left(self):
        dealer = Player("John")
        bidding = Bidding(self.players, dealer)
        expected = Player("Mom")
        actual = bidding.player_to_dealers_left()
        self.assertEqual(expected, actual)

    def test_pass_init(self):
        bidding = Bidding(self.players, self.players[0])
        self.assertFalse(bidding.all_pass())

    def test_pass_a_few(self):
        bidding = Bidding(self.players, self.players[0])
        bidding.bids["John"].append(PASS)
        self.assertFalse(bidding.all_pass())

    def test_pass_all(self):
        bidding = Bidding(self.players, self.players[0])
        bidding.bids["John"].append(PASS)
        bidding.bids["Ellie"].append(PASS)
        bidding.bids["Dad"].append(PASS)
        bidding.bids["Mom"].append(PASS)
        self.assertTrue(bidding.all_pass())
