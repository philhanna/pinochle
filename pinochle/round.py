from itertools import cycle
from typing import List

from pinochle import Player, Deck, Hand


class Round:
    """ One round of play """

    def __init__(self, players: List[Player], dealer: Player):
        """ Starts a round """
        self.players: List[Player] = players
        self.dealer: Player = dealer

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
