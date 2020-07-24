from enum import IntEnum

from pinochle import Rank, Suit


class Card:
    """ A card in the pinochle deck """

    def __init__(self, rank: Rank, suit: Suit):
        self.rank = rank
        self.suit = suit

    @staticmethod
    def parse(s):
        """ Parses the input string for a card name """
        return CardParser.parse(s)

    def __str__(self):
        rankname = self.rank.fullname()
        suitname = self.suit.value.lower()
        output = f"{rankname} of {suitname}"
        return output

    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        return hash(self.rank) ^ hash(self.suit)

class CardParser:
    """ Parses an input string for a card name """

    @staticmethod
    def parse(s):

        rank = None
        suit = None

        def check_first_letter(ch):
            nonlocal rank, suit
            if ch == '1':
                state = State.AFTER_1
            elif ch not in "AKQJ9":
                state = State.ERROR
            else:
                rankmap = {
                    'A': Rank.ACE,
                    'K': Rank.KING,
                    'Q': Rank.QUEEN,
                    'J': Rank.JACK,
                    '9': Rank.NINE
                }
                rank = rankmap[ch]
                state = State.AFTER_RANK
            return state

        def check_for_zero(ch):
            nonlocal rank, suit
            if ch == '0':
                rank = Rank.TEN
                state = State.AFTER_RANK
            else:
                state = State.ERROR
            return state

        def check_for_suit(ch):
            nonlocal rank, suit
            if ch not in "HCDS":
                state = State.ERROR
            else:
                suitmap = {
                    'S': Suit.SPADES,
                    'H': Suit.HEARTS,
                    'D': Suit.DIAMONDS,
                    'C': Suit.CLUBS
                }
                suit = suitmap[ch]
                state = State.GOT_IT
            return state

        transitions = {
            State.INIT: check_first_letter,
            State.AFTER_1: check_for_zero,
            State.AFTER_RANK: check_for_suit
        }

        state = State.INIT
        for ch in s.upper():
            state = transitions[state](ch)
            if state == State.ERROR:
                return None
            if state == State.GOT_IT:
                return Card(rank, suit)


class State(IntEnum):
    """ Used in the parse method """
    INIT = 0
    AFTER_1 = 1
    AFTER_RANK = 2
    ERROR = 3
    GOT_IT = 4
