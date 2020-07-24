from itertools import groupby

from pinochle import Suit


class Hand:
    """ The list of cards in a player's hand """

    def __init__(self):
        """ We use a list rather than a set because there can be duplicates """
        self._cards = []

    @property
    def cards(self):
        return self._cards

    def add(self, card):
        self._cards.append(card)

    def organized(self):
        """ Returns a map of suits to cards in that suit, descending """
        def cardkey(card):
            return card.suit.name, card.rank.order()

        cards = sorted(self.cards, key=cardkey, reverse=True)
        mymap = {}
        for k, g in groupby(cards, key=lambda card: card.suit.value):
            mymap[k] = list(g)
        return mymap
