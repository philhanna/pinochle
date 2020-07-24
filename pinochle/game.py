from collections import defaultdict

from pinochle import Deck


class Game:
    """ A pinochle game """
    def __init__(self, players):
        self.players = players

    def choose_dealer(self):
        """ Chooses the dealer """
        deck = Deck()
        deck.shuffle()
        loop_limit = 32
        for attempt in range(loop_limit):  # Limit to prevent runaway loop
            cards = deck.cards.copy() # Copy because we are going to remove cards
            players_choosing = defaultdict(list)
            for player in self.players:
                card = player.choose_card(cards)
                players_choosing[card.rank].append(player)
                cards.remove(card)
            # Choose the highest of the rank orders
            highest_rank = max(players_choosing.keys(), key=lambda rank: rank.order())
            high_players = players_choosing[highest_rank]
            if len(high_players) == 1:
                dealer = high_players[0]
                return dealer

        errmsg = f"No highest card chosen after {loop_limit} attempts"
        raise RuntimeError(errmsg)
