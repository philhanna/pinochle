import re
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
        rankname: str = str(self.rank)
        suitname: str = str(self.suit)
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
        card = None
        m = re.match(r'([A1KQJ9]).* OF ([HCDS]).*', s.upper())
        if m:
            rank_key = m.group(1)
            suit_key = m.group(2)
            rank, suit = rankmap.get(rank_key), suitmap.get(suit_key)
            card = Card(rank, suit)
        return card


rankmap: Dict[str, Rank] = {
    "A": Rank.ACE,
    "1": Rank.TEN,
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
