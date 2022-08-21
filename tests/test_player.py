from unittest import TestCase

from pinochle import Player, CardParser, Card, Rank, Suit


class TestPlayer(TestCase):

    def setUp(self):
        self.player = Player("John Doe")

    def tearDown(self) -> None:
        del self.player

    def test_init(self):
        player1 = self.player
        player2 = Player("John Doe")
        self.assertEqual(player1.name, player2.name)

    def test_add_card_to_hand(self):
        player = self.player
        player.add_card_to_hand(CardParser.parse("Queen of Spades"))
        player.add_card_to_hand(CardParser.parse("Jack of Diamonds"))
        actual: list[Card] = player.cards
        expected: list[Card] = [Card(Rank.QUEEN, Suit.SPADES), Card(Rank.JACK, Suit.DIAMONDS)]
        self.assertEqual(expected, actual)

    def test_partner(self):
        cat = Player("Catherine Wood")
        self.player.partner = cat
        expected = cat
        actual = self.player.partner
        self.assertEqual(expected, actual)

    def test_repr(self):
        expected = "Player(\"John Doe\")"
        actual = repr(self.player)
        self.assertEqual(expected, actual)

    def test_str(self):
        expected = "John Doe"
        actual = str(self.player)
        self.assertEqual(expected, actual)

    def test_eq(self):
        player1 = self.player
        player2 = Player("John Doe")
        self.assertEqual(str(player1), str(player2))
        self.assertIs(player1, player1)
        self.assertIs(player2, player2)
        self.assertIsNot(player1, player2)