from random import choice


class DealerChoosingStrategy:
    """ Given a list of cards, chooses one """

    def choose_card(self, cards):
        """ Chooses a card """
        return choice(cards)
