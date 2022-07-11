from collections import defaultdict
from typing import List

from pinochle import Deck, Player, Card, Rank


class Game:
    """ A pinochle game """
    def __init__(self, players: List[Player]):
        self.players: List[Player] = players

    def choose_dealer(self):
        """ Chooses the dealer """
        deck = Deck()
        deck.shuffle()
        loop_limit = 32
        for attempt in range(loop_limit):  # Limit to prevent runaway loop
            cards: [Card] = deck.cards.copy() # Copy because we are going to remove cards
            players_that_chose: defaultdict[Rank] = defaultdict(list)
            for player in self.players:
                card = player.choose_card(cards)
                players_that_chose[card.rank].append(player)
                cards.remove(card)
            # Choose the highest of the rank orders
            highest_rank: Rank = max(players_that_chose.keys(), key=lambda rank: rank.order())
            high_players: List[Player] = players_that_chose[highest_rank]
            if len(high_players) == 1:
                dealer = high_players[0]
                return dealer

        errmsg = f"No highest card chosen after {loop_limit} attempts"
        raise RuntimeError(errmsg)
