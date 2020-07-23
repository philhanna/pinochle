class Player:
    """ One of the four players in the game """
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"{__class__.__name__}(\"{self.name}\")"

    def __str__(self):
        return self.name
