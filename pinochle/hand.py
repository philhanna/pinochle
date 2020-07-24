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
        cards = sorted(self.cards, key=lambda x: (x.suit.name, x.rank.order()), reverse=True)
        return {k:list(g) for k, g in groupby(cards, key=lambda card: card.suit.value)}

    def __str__(self):
        entries = []
        for k, v in self.organized().items():
            line = k + ":" + " ".join([card.rank.value for card in v])
            entries.append(line)
        return "\n".join(entries)
