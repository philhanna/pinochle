from itertools import cycle

from pinochle import Player, Deck, Hand


class Round:
    """ One round of play """

    def __init__(self, players, dealer):
        """ Starts a round """
        self.players = players
        self.dealer = dealer

    def player_iterator(self):
        """ Creates an iterator for the players that follow the dealer """

        players = self.players
        dealer = self.dealer
        d = players.index(dealer)
        if d == -1:
            errmsg = f"Dealer {self.dealer} is not one of the players"
            raise ValueError(errmsg)
        d = (d + 1) % 4
        return cycle(self.players[d:] + self.players[0:d])

    def deal(self):
        """ Deals each player a hand """

        # Empty hands for each player to begin with
        players = self.players
        for player in players:
            player.hand = Hand()

        # Shuffle and deal
        deck = Deck()
        deck.shuffle()
        it = self.player_iterator()
        for card in deck.cards:
            player = next(it)
            player.hand.add(card)

    def do_bidding(self):
        """ Runs the bidding for this round.

        Bidding starts with the player to the dealer's left.
        Opening bid must be 250 or greater.
        Subsequent bids must be either:
        - Pass, or
        - A multiple of 10 that is greater than the previous bid
        The bidding ends when all but one player has passed.
        If all four players pass on the first go around, the
        round is cancelled.
        Also, if only the first player bid, he has the the option
        to cancel.
        """
        bids = { player:0 for player in self.players }
        pass
