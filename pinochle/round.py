from itertools import cycle

from pinochle import Player, Team, Deck, Hand


class Round:
    """ One round of play """

    def __init__(self, teams, dealer):
        """ Starts a round """
        self.teams = teams
        self.players = [[player for player in team.players] for team in teams]
        self.dealer = dealer

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

    def player_iterator(self):
        """ Creates an iterator for the players that follow the dealer """

        d = self.players.index(self.dealer)
        if d == -1:
            errmsg = f"Dealer {self.dealer} is not one of the players"
            raise ValueError(errmsg)
        d = (d + 1) % 4
        return cycle(self.players[d:] + self.players[0:d])
