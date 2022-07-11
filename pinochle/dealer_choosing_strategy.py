from random import choice
from typing import List

from pinochle import Card


class DealerChoosingStrategy:
    """ Given a list of cards, chooses one """

    def choose_card(self, cards: List[Card]) -> Card:
        """ Chooses a card """
        card: Card = choice(cards)
        return card
