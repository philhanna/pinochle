from typing import Optional, Dict

from pinochle import Suit, Rank

class Card:
    """ A card in the pinochle deck """

    def __init__(self, rank: Rank, suit: Suit):
        self.rank: Rank = rank
        self.suit: Suit = suit

    @staticmethod
    def parse(s) -> "Card":
        """ Parses the input string for a card object """
        return CardParser.parse(s)

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        """ Gets the english language representation of this card with title case words """
        rankname: str = self.rank.fullname().title()
        suitname: str = self.suit.value.lower().title()
        output: str = f"{rankname} of {suitname}"
        return output

    def __eq__(self, other) -> bool:
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self) -> int:
        return hash(self.rank) ^ hash(self.suit)


class CardParser:
    """ Parses an input string for a card name """

    @staticmethod
    def parse(s: str) -> Optional[Card]:
        rank: Optional[Rank] = None
        state: int = 0

        for ch in s.upper():

            # To begin with, we are looking for the start of a rank name
            if state == 0:
                if ch == '1':
                    state = 1
                elif ch not in "AKQJ9":
                    return None
                else:
                    rank = rankmap[ch]
                    state = 2

            # After a "1", we are expecting a "0" to get a rank of TEN
            elif state == 1:
                if ch == '0':
                    rank = Rank.TEN
                    state = 2
                else:
                    return None

            # After the rank is known, look for the first letter of a suit name
            elif state == 2:
                if ch not in "HCDS":
                    return None
                return Card(rank, suitmap[ch])


rankmap: Dict[str, Rank] = {
    "A": Rank.ACE,
    "K": Rank.KING,
    "Q": Rank.QUEEN,
    "J": Rank.JACK,
    "9": Rank.NINE
}

suitmap: Dict[str, Suit] = {
    'H': Suit.HEARTS,
    'C': Suit.CLUBS,
    'D': Suit.DIAMONDS,
    'S': Suit.SPADES
}
