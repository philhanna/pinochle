class Team:
    """ A pair of players """
    def __init__(self, player1, player2):
        self.player1 = player1
        self.player2 = player2
        self.score = 0

    @property
    def players(self):
        return [self.player1, self.player2]

    def __str__(self):
        return f"{self.player1} and {self.player2}"
