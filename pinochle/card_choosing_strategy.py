from random import random


class CardChoosingStrategy:
    """ Given a list of cards, chooses one """

    def choose_card(self, cards):
        """ Chooses a card """
        return random.choice(cards)
