from pinochle import Player, Team
from typing import List


class Round:
    """ One round of play """

    def __init__(self, teams: List[Team], dealer: Player):
        self.teams = teams
        self.dealer = dealer
        pass
