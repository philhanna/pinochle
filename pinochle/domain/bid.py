# pinochle.domain.bid
from dataclasses import dataclass

MINIMUM_BID = 250
BID_INCREMENT = 10


def is_valid_bid(amount: int, current_high: int) -> bool:
    """Return True if `amount` is a valid new bid above `current_high`."""
    if amount < MINIMUM_BID:
        return False
    if amount % BID_INCREMENT != 0:
        return False
    return amount > current_high


@dataclass
class BidEntry:
    """A single bid or pass submitted by one player during the bidding phase.

    Attributes:
        player_id: The player who made this bid or pass.
        amount: The bid value, or ``None`` when the player passed.  A ``None``
            amount means the player is removed from subsequent bidding.
    """

    player_id: str
    amount: int | None  # None = pass


class BiddingRound:
    """Manages one complete round of bidding for the four players at the table.

    Players bid in clockwise order starting from the player to the left of
    the dealer.  Each bid must exceed the current high bid by at least one
    increment and meet the minimum opening bid.  Passing removes a player
    from further bidding.  Bidding concludes automatically once only one
    active bidder remains; at that point ``is_over`` is ``True`` and
    ``high_bidder`` identifies the bid winner.

    Raises ``ValueError`` on any out-of-turn or invalid action, preserving
    the existing state so callers can handle the error and retry.
    """

    def __init__(self, player_order: list[str]):
        """Initialize bidding state for the provided clockwise turn order."""
        if len(player_order) != 4:
            raise ValueError("Exactly four players required.")
        self._order: list[str] = list(player_order)
        self._passed: set[str] = set()
        self._history: list[BidEntry] = []
        self._current_high: int = 0
        self._turn: int = 0

    @property
    def current_high(self) -> int:
        """Return the current highest bid amount."""
        return self._current_high

    @property
    def high_bidder(self) -> str | None:
        """Return the player who most recently placed a non-pass bid."""
        for entry in reversed(self._history):
            if entry.amount is not None:
                return entry.player_id
        return None

    @property
    def active_players(self) -> list[str]:
        """Return players who have not yet passed."""
        return [p for p in self._order if p not in self._passed]

    @property
    def is_over(self) -> bool:
        """Return ``True`` once no further bid can be made.

        A single remaining bidder ends the auction only if a bid has actually
        been placed.  When the other three pass without anyone opening, the
        last player still gets their turn: they may open the bidding or pass
        and throw the round in.
        """
        active = self.active_players
        if not active:
            return True
        if len(active) > 1:
            return False
        return self.bid_count > 0

    @property
    def bid_count(self) -> int:
        """Return how many actual bids, as opposed to passes, have been made."""
        return sum(1 for entry in self._history if entry.amount is not None)

    @property
    def current_bidder(self) -> str | None:
        """Return the player whose turn it is, or ``None`` once bidding is over."""
        if self.is_over:
            return None
        return self._order[self._turn]

    def place_bid(self, player_id: str, amount: int | None) -> None:
        """Record a bid (amount=None means pass).

        Raises ValueError for an out-of-turn or invalid bid.
        """
        if self.is_over:
            raise ValueError("Bidding is already over.")
        if player_id not in self.active_players:
            raise ValueError(f"{player_id} is not an active bidder.")
        if player_id != self.current_bidder:
            raise ValueError(f"It is {self.current_bidder}'s turn to bid.")

        if amount is None:
            self._passed.add(player_id)
        else:
            if not is_valid_bid(amount, self._current_high):
                raise ValueError(
                    f"Bid of {amount} is invalid (current high: {self._current_high})."
                )
            self._current_high = amount

        self._history.append(BidEntry(player_id=player_id, amount=amount))
        self._advance_turn()

    def _advance_turn(self) -> None:
        """Move the turn to the next player who has not yet passed."""
        if self.is_over:
            return
        for _ in range(len(self._order)):
            self._turn = (self._turn + 1) % len(self._order)
            if self._order[self._turn] not in self._passed:
                return
