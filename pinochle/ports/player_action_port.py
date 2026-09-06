# pinochle.ports.player_action_port
from abc import ABC, abstractmethod

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit


class PlayerActionPort(ABC):
    """Player-facing game actions exposed by the application layer.

    This port defines the boundary between the application core and any
    delivery mechanism (web API, CLI, AI agent, etc.) that drives player
    decisions.  Each method corresponds to a distinct phase of a Pinochle
    round and must be called in the order dictated by the game state machine.
    """

    @abstractmethod
    def draw_for_deal(self, game_id: str, player_id: str, position: int) -> Card:
        """Take one card from the face-down spread to determine the dealer.

        The spread is a single shuffled deck of 48 addressable positions, so a
        position taken by one player is unavailable to the others.  Each player
        draws once; the highest card deals.  A tie on rank restarts the whole
        draw with a fresh spread — suit never breaks it.

        Args:
            game_id: Unique identifier of the game session.
            player_id: Unique identifier of the player drawing the card.
            position: Index of the chosen card in the spread.

        Returns:
            The card lying at that position.
        """

    @abstractmethod
    def place_bid(self, game_id: str, player_id: str, amount: int | None) -> None:
        """Submit a bid or pass during the bidding phase.

        Players bid in turn, starting left of the dealer.  A bid must be
        higher than the current high bid; passing removes the player from
        subsequent bidding rounds.  Bidding ends when all but one player have
        passed, and the remaining player wins the bid at their last stated
        amount.

        Args:
            game_id: Unique identifier of the game session.
            player_id: Unique identifier of the bidding player.
            amount: The bid value, which must exceed the current high bid, or
                ``None`` to pass.
        """

    @abstractmethod
    def name_trump(self, game_id: str, player_id: str, suit: Suit) -> None:
        """Declare the trump suit after winning the bid.

        Only the bid winner may call this method.  The chosen suit becomes
        trump for the entire round and affects meld scoring and trick-taking.
        This call transitions the game into the card-passing phase.

        Args:
            game_id: Unique identifier of the game session.
            player_id: Unique identifier of the bid-winning player.
            suit: The suit to designate as trump for this round.
        """

    @abstractmethod
    def pass_cards(self, game_id: str, player_id: str, cards: list[Card]) -> None:
        """Pass four cards to the bidding team's partner.

        After trump is named, the bid winner selects exactly four cards from
        their hand to send to their partner.  The partner then returns four
        cards in exchange.  This call is invalid outside the passing phase or
        if ``cards`` does not contain exactly four cards held by the player.

        Args:
            game_id: Unique identifier of the game session.
            player_id: Unique identifier of the passing player.
            cards: Exactly four cards from the player's current hand to pass.
        """

    @abstractmethod
    def play_card(self, game_id: str, player_id: str, card: Card) -> None:
        """Play a card into the current trick during trick-taking.

        The player must follow suit if able; otherwise any card may be played.
        After all four players have played, the trick is awarded to the
        highest trump (or highest card of the led suit if no trump was played),
        and the winner leads the next trick.

        Args:
            game_id: Unique identifier of the game session.
            player_id: Unique identifier of the playing player.
            card: A card from the player's hand to play into the current trick.
        """

    @abstractmethod
    def confirm_contract(self, game_id: str, player_id: str, accept: bool) -> None:
        """Take or decline a contract won without opposition.

        Offered only when a single player bid and the other three passed.
        Accepting proceeds to naming trump; declining abandons the round with
        no change to either score, and the deal moves on.

        Args:
            game_id: Unique identifier of the game session.
            player_id: The lone bidder being offered the choice.
            accept: ``True`` to take the contract, ``False`` to decline it.
        """
