class Game:
    """The server side (model) of the application.

    Game has a list of four players, arranged in partner order.
    That is, players 0 and 2 are partners, as are players 1 and 3.
    Once the 'start' command is received (from the administrator),
    the game does this:

    - Opens a server socket for each player
    - Assigns the dealer
    Then for each hand:
        - Shuffles the deck and deals each player his cards
        - Accepts bids from each player until there is only one left
        - Keeps track of the bid amount
        - Accepts the trump suit from the bid winner
        - Accepts four cards from the bid winner and passes them to his partner
        - Accepts four cards from the bid winner's partner and passes them back
        - Accepts meld from each player
        - Initiates play:
           - Accepts card from each player in turn
           - Determine who wins the trick and stores the four cars in a "trick"
        - Calculates the points won by each partner team
        - Updates the score
        - Exits if a partner team has won 2000 points or more
        - Otherwise, rotates dealer to the player on the current dealer's left


    """
    def __init__(self):
        pass
