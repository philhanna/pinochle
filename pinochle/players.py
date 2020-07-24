class Players:
    """ A list of four players """
    def __init__(self, *players):
        """ Creates the player list from a list of four players """
        if len(players) != 4:
            errmsg = f"Number of players must be 4, not {len(players)}"
            raise ValueError(errmsg)
        self.players = players

    def next_player(self, player=None):
        """ Given a player, returns the next player around the table.

        :param player. If specified, the iterator starts with this player.
        Default is player[0]
         """
        if not player:
            return self.players[0]

        if player not in self.players:
            errmsg = f"{player} is not in the player set"
            raise ValueError(errmsg)
        p = self.players.index(player)
        p = (p + 1) % 4
        return self.players[p]
