from enum import Enum


class Rank(Enum):
    NINE = 1,
    JACK = 2,
    QUEEN = 3,
    KING = 4,
    TEN = 5,
    ACE = 6,
    
    def short_name(self):
        SHORT_NAMES = {
            Rank.NINE: "9",
            Rank.JACK: "J",
            Rank.QUEEN: "Q",
            Rank.KING: "K",
            Rank.TEN: "10",
            Rank.ACE: "A",
        }
        return SHORT_NAMES[self]
    
    def rank_name(self):
        RANK_NAMES = {
            Rank.NINE: "9",
            Rank.JACK: "jack",
            Rank.QUEEN: "queen",
            Rank.KING: "king",
            Rank.TEN: "10",
            Rank.ACE: "ace",
        }
        return RANK_NAMES[self]
        