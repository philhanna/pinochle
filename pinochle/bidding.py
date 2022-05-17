from itertools import cycle


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
    Also, if only the first player bid, he has the the option
    to cancel.
    """
    def __init__(self, players):
        self.players = players
        self.bids = {player.name: None for player in players}

    def start(self):
        """
        Starts a round of bidding
        """
        pass
