class Bidding:
    pass

def do_bidding(self):
    """ Runs the bidding for this round.

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
    bids = {player: None for player in self.players}
    bidding_round = 1
    it = self.player_iterator()
    first_bidder = next(it)
    pass
