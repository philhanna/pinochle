from unittest import TestCase

from pinochle import Player, CardParser, Card, Rank, Suit


class TestPlayer(TestCase):

    def test_init(self):
        player1 = Player("John Doe")
        player2 = Player("John Doe")
        self.assertEqual(player1.name, player2.name)

    def test_add_card_to_hand(self):
        player = Player("John Doe")
        player.add_card_to_hand(CardParser.parse("Queen of Spades"))
        player.add_card_to_hand(CardParser.parse("Jack of Diamonds"))
        actual: list[Card] = player.cards
        expected: list[Card] = [Card(Rank.QUEEN, Suit.SPADES), Card(Rank.JACK, Suit.DIAMONDS)]
        self.assertEqual(expected, actual)