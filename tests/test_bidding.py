from unittest import TestCase

from pinochle import Bidding, Player


class TestBidding(TestCase):

    def setUp(self):
        self.players = [
            Player("John"),
            Player("Ellie"),
            Player("Dad"),
            Player("Mom"),
        ]
        pass

    def test_bids(self):
        bidding = Bidding(self.players)
        print(bidding.bids)
