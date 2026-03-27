# pinochle.services.round
from enum import Enum, auto

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.deck import Deck
from pinochle.domain.cards.suit import Suit
from pinochle.domain.hand import Hand
from pinochle.domain.bid import BiddingRound
from pinochle.domain.trick import Trick


class RoundPhase(Enum):
    """Detailed lifecycle states for a single round of play.

    States advance strictly forward through the sequence:
    ``DEALING`` → ``BIDDING`` → ``TRUMP`` → ``PASSING`` → ``MELDING`` →
    ``PLAYING`` → ``SCORING`` → ``COMPLETE``.

    - ``DEALING``: Cards are being distributed to all players.
    - ``BIDDING``: Players are submitting bids or passing.
    - ``TRUMP``: The bid winner is declaring the trump suit.
    - ``PASSING``: The bid winner and partner exchange four cards each.
    - ``MELDING``: Players declare meld combinations from their hands.
    - ``PLAYING``: Trick-taking is in progress.
    - ``SCORING``: The round has ended and scores are being tallied.
    - ``COMPLETE``: The round is fully resolved.
    """

    DEALING = auto()
    BIDDING = auto()
    TRUMP = auto()
    PASSING = auto()
    MELDING = auto()
    PLAYING = auto()
    SCORING = auto()
    COMPLETE = auto()


class Round:
    """One round of Pinochle play.

    Drives the state machine: DEALING → BIDDING → TRUMP → PASSING →
    MELDING → PLAYING → SCORING → COMPLETE.
    """

    HAND_SIZE = 12
    PASS_COUNT = 4

    def __init__(self, dealer_id: str, player_order: list[str]):
        """
        Args:
            dealer_id: Player who deals this round.
            player_order: All four player IDs in clockwise seat order
                          starting from North/seat-0.
        """
        if len(player_order) != 4:
            raise ValueError("Exactly four players required.")
        self.dealer_id = dealer_id
        self.player_order = list(player_order)
        self.phase = RoundPhase.DEALING

        self._deck = Deck()
        self._hands: dict[str, Hand] = {p: Hand() for p in player_order}
        self._bidding: BiddingRound | None = None
        self._trump: Suit | None = None
        self._bid_winner: str | None = None
        self._contract: int | None = None
        self._tricks: list[Trick] = []
        self._current_trick: Trick | None = None
        self._next_leader: str | None = None

        # Passing state
        self._pending_pass: dict[str, list[Card]] = {}

    # ------------------------------------------------------------------
    # Phase: DEALING
    # ------------------------------------------------------------------

    def deal(self) -> None:
        """Shuffle and deal 12 cards to each player."""
        if self.phase != RoundPhase.DEALING:
            raise ValueError(f"Cannot deal in phase {self.phase}.")
        self._deck.shuffle()
        dealer_idx = self.player_order.index(self.dealer_id)
        # Deal starts to the left of the dealer, 3 cards at a time
        order = self.player_order[(dealer_idx + 1) % 4:] + self.player_order[:(dealer_idx + 1) % 4]
        while len(self._deck) >= 3:
            for player_id in order:
                self._hands[player_id].add(self._deck.deal(3))
        self.phase = RoundPhase.BIDDING
        # First to bid is left of dealer
        bid_order = order  # already starts left of dealer
        self._bidding = BiddingRound(bid_order)

    # ------------------------------------------------------------------
    # Phase: BIDDING
    # ------------------------------------------------------------------

    def place_bid(self, player_id: str, amount: int | None) -> None:
        """Submit a bid or pass during the bidding phase."""
        if self.phase != RoundPhase.BIDDING:
            raise ValueError(f"Cannot bid in phase {self.phase}.")
        self._bidding.place_bid(player_id, amount)
        if self._bidding.is_over:
            self._bid_winner = self._bidding.high_bidder
            self._contract = self._bidding.current_high
            self.phase = RoundPhase.TRUMP

    # ------------------------------------------------------------------
    # Phase: TRUMP
    # ------------------------------------------------------------------

    def name_trump(self, player_id: str, suit: Suit) -> None:
        """Set the trump suit after bidding completes."""
        if self.phase != RoundPhase.TRUMP:
            raise ValueError(f"Cannot name trump in phase {self.phase}.")
        if player_id != self._bid_winner:
            raise ValueError("Only the bid winner names trump.")
        self._trump = suit
        self.phase = RoundPhase.PASSING

    # ------------------------------------------------------------------
    # Phase: PASSING
    # ------------------------------------------------------------------

    def _partner_of(self, player_id: str) -> str:
        """Return the partner seated across from ``player_id``."""
        idx = self.player_order.index(player_id)
        return self.player_order[(idx + 2) % 4]

    def pass_cards(self, player_id: str, cards: list[Card]) -> None:
        """Bid winner passes 4 cards to partner; partner passes 4 back."""
        if self.phase != RoundPhase.PASSING:
            raise ValueError(f"Cannot pass cards in phase {self.phase}.")
        if len(cards) != self.PASS_COUNT:
            raise ValueError(f"Must pass exactly {self.PASS_COUNT} cards.")
        partner = self._partner_of(player_id)
        for card in cards:
            if card not in self._hands[player_id]:
                raise ValueError(f"{player_id} does not hold {card}.")
        self._hands[player_id].remove_many(cards)
        self._pending_pass[player_id] = cards
        # Both directions complete?
        if len(self._pending_pass) == 2:
            for giver, given in self._pending_pass.items():
                receiver = self._partner_of(giver)
                self._hands[receiver].add(given)
            self._pending_pass.clear()
            self.phase = RoundPhase.MELDING

    # ------------------------------------------------------------------
    # Phase: MELDING (declarative — caller detects meld externally)
    # ------------------------------------------------------------------

    def advance_to_playing(self) -> None:
        """Move from meld declaration into trick-taking play."""
        if self.phase != RoundPhase.MELDING:
            raise ValueError(f"Cannot advance to playing from phase {self.phase}.")
        self.phase = RoundPhase.PLAYING
        self._next_leader = self._bid_winner

    # ------------------------------------------------------------------
    # Phase: PLAYING
    # ------------------------------------------------------------------

    def play_card(self, player_id: str, card: Card) -> str | None:
        """Play a card. Returns winner player_id when trick completes, else None."""
        if self.phase != RoundPhase.PLAYING:
            raise ValueError(f"Cannot play in phase {self.phase}.")
        if card not in self._hands[player_id]:
            raise ValueError(f"{player_id} does not hold {card}.")

        if self._current_trick is None:
            if player_id != self._next_leader:
                raise ValueError(f"It is {self._next_leader}'s turn to lead.")
            self._current_trick = Trick(lead_player_id=player_id, trump=self._trump)

        self._current_trick.play(player_id, card)
        self._hands[player_id].remove(card)

        if self._current_trick.is_complete:
            winner_id = self._current_trick.winner()
            self._tricks.append(self._current_trick)
            self._current_trick = None
            self._next_leader = winner_id
            if all(len(h) == 0 for h in self._hands.values()):
                self.phase = RoundPhase.SCORING
            return winner_id

        return None

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def hand(self, player_id: str) -> Hand:
        """Return the mutable hand object for ``player_id``."""
        return self._hands[player_id]

    @property
    def tricks(self) -> list[Trick]:
        """Return a copy of the completed tricks so far."""
        return list(self._tricks)

    @property
    def trump(self) -> Suit | None:
        """Return the trump suit once it has been named."""
        return self._trump

    @property
    def bid_winner(self) -> str | None:
        """Return the player who won the bidding."""
        return self._bid_winner

    @property
    def contract(self) -> int | None:
        """Return the winning bid amount for the round."""
        return self._contract
