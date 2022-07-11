from itertools import cycle

from typing import List, Dict

from pinochle import Player, PASS


class Bidding:
    """
    Bidding starts with the player to the dealer's left.
    Opening bid must be 250 or greater.
    Subsequent bids must be either:

    - Pass, or
    - A multiple of 10 that is greater than the previous bid

    The bidding ends when all but one player has passed.
    If all four players pass on the first go around, the
    round is canceled.
    Also, if only the first player bid, he has the option
    to cancel.
    """

    def __init__(self, players: List[Player], dealer: Player):
        if dealer not in players:
            raise ValueError(f"{dealer} is not in the list of players")
        self.players: List[Player] = players
        self.dealer: Player = dealer
        self.bids: Dict[str, List[int]] = {player.name: [] for player in players}

    def player_to_dealers_left(self) -> Player:
        k: int = self.players.index(self.dealer)
        km1 = k - 1
        if km1 < 0:
            km1 += len(self.players)
        player = self.players[km1]
        return  player

    def all_pass(self) -> bool:
        """ A boolean function that returns True if all players
        have PASS as their last bid """
        pass_count = 0
        for player in self.players:
            player_bids: List[int] = self.bids[player.name]
            if player_bids and player_bids[-1] == PASS:
                pass_count += 1
        return pass_count == 4
