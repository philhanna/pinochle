# pinochle.services.round
from enum import Enum, auto

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.deck import Deck
from pinochle.domain.cards.suit import Suit
from pinochle.domain.hand import Hand
from pinochle.domain.bid import BiddingRound
from pinochle.domain.meld import MeldUnit, detect_meld
from pinochle.domain.trick import Trick


class RoundPhase(Enum):
    """Detailed lifecycle states for a single round of play.

    States advance strictly forward through the sequence:
    ``DEALING`` → ``BIDDING`` → ``TRUMP`` → ``PASSING`` → ``MELDING`` →
    ``PLAYING`` → ``SCORING`` → ``COMPLETE``.

    - ``DEALING``: Cards are being distributed to all players.
    - ``BIDDING``: Players are submitting bids or passing.
    - ``CONFIRMING``: A lone bidder is deciding whether to take the contract.
    - ``ABANDONED``: The round ended before play, leaving all scores unchanged.
    - ``TRUMP``: The bid winner is declaring the trump suit.
    - ``PASSING``: The bid winner and partner exchange four cards each.
    - ``MELDING``: Each player's meld is exposed and held on screen. No player
      acts during this phase; it ends on a server-owned timer.
    - ``PLAYING``: Trick-taking is in progress.
    - ``SCORING``: The round has ended and scores are being tallied.
    - ``COMPLETE``: The round is fully resolved.
    """

    DEALING = auto()
    BIDDING = auto()
    CONFIRMING = auto()
    ABANDONED = auto()
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

        # Passing state: who has already sent their four cards.
        self._passed_cards: dict[str, list[Card]] = {}

        # Meld, captured once at the end of PASSING and never recomputed,
        # because the cards leave the hands during trick play.
        self._meld: dict[str, list[MeldUnit]] = {}

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
        if not self._bidding.is_over:
            return

        self._bid_winner = self._bidding.high_bidder
        self._contract = self._bidding.current_high
        if self._bid_winner is None:
            # FR-31: nobody bid, so the round is thrown in.
            self.phase = RoundPhase.ABANDONED
        elif self._bidding.bid_count == 1:
            # FR-32: a lone bidder may decline rather than be held to it.
            self.phase = RoundPhase.CONFIRMING
        else:
            self.phase = RoundPhase.TRUMP

    # ------------------------------------------------------------------
    # Phase: CONFIRMING
    # ------------------------------------------------------------------

    def confirm_contract(self, player_id: str, accept: bool) -> None:
        """Take or decline a contract won without anyone bidding against you."""
        if self.phase != RoundPhase.CONFIRMING:
            raise ValueError(f"Cannot confirm a contract in phase {self.phase}.")
        if player_id != self._bid_winner:
            raise ValueError("Only the lone bidder may accept or decline.")
        if accept:
            self.phase = RoundPhase.TRUMP
            return
        self._bid_winner = None
        self._contract = None
        self.phase = RoundPhase.ABANDONED

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

    def partner_of(self, player_id: str) -> str:
        """Return the partner seated across from ``player_id``."""
        idx = self.player_order.index(player_id)
        return self.player_order[(idx + 2) % 4]

    def pass_cards(self, player_id: str, cards: list[Card]) -> None:
        """Pass four cards to a partner, the auction winner's partner going first.

        The exchange is strictly ordered (FR-42), so the cards arrive before
        the auction winner chooses what to send back and their choice is an
        informed one — they are holding sixteen cards when they make it.
        """
        if self.phase != RoundPhase.PASSING:
            raise ValueError(f"Cannot pass cards in phase {self.phase}.")
        if player_id != self.current_player:
            raise ValueError(f"It is {self.current_player}'s turn to pass.")
        if len(cards) != self.PASS_COUNT:
            raise ValueError(f"Must pass exactly {self.PASS_COUNT} cards.")
        for card in cards:
            if card not in self._hands[player_id]:
                raise ValueError(f"{player_id} does not hold {card}.")

        self._hands[player_id].remove_many(cards)
        self._hands[self.partner_of(player_id)].add(cards)
        self._passed_cards[player_id] = cards

        if len(self._passed_cards) == 2:
            self._capture_meld()
            self.phase = RoundPhase.MELDING

    def _capture_meld(self) -> None:
        """Record every player's meld from their hand as it stands after the pass."""
        self._meld = {
            player_id: detect_meld(list(hand), self._trump)
            for player_id, hand in self._hands.items()
        }

    # ------------------------------------------------------------------
    # Phase: MELDING
    # ------------------------------------------------------------------

    def advance_to_playing(self) -> None:
        """End the meld display and begin trick-taking."""
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
        if player_id != self.current_player:
            raise ValueError(f"It is {self.current_player}'s turn to play.")
        if card not in self._hands[player_id]:
            raise ValueError(f"{player_id} does not hold {card}.")
        if card not in self.legal_plays(player_id):
            raise ValueError(f"{card} is not a legal play for {player_id}.")

        if self._current_trick is None:
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

    @property
    def current_player(self) -> str | None:
        """Return the player who must act next, or ``None`` if nobody is on the clock.

        DEALING, MELDING, SCORING and COMPLETE are driven by the server rather
        than by a player, so they have no current player.
        """
        if self.phase == RoundPhase.BIDDING:
            return self._bidding.current_bidder
        if self.phase == RoundPhase.CONFIRMING:
            return self._bid_winner
        if self.phase == RoundPhase.TRUMP:
            return self._bid_winner
        if self.phase == RoundPhase.PASSING:
            return self._next_passer()
        if self.phase == RoundPhase.PLAYING:
            return self._next_to_play()
        return None

    def _next_passer(self) -> str | None:
        """Return whoever still owes a pass, the partner going first."""
        partner = self.partner_of(self._bid_winner)
        if partner not in self._passed_cards:
            return partner
        if self._bid_winner not in self._passed_cards:
            return self._bid_winner
        return None

    def _next_to_play(self) -> str | None:
        """Return the player due to play into the current trick."""
        if self._current_trick is None:
            return self._next_leader
        idx = self.player_order.index(self._next_leader)
        return self.player_order[(idx + len(self._current_trick.cards)) % 4]

    def legal_plays(self, player_id: str) -> list[Card]:
        """Return the cards ``player_id`` may legally play into the current trick."""
        return self._hands[player_id].legal_plays(self._current_trick, self._trump)

    def hand(self, player_id: str) -> Hand:
        """Return the mutable hand object for ``player_id``."""
        return self._hands[player_id]

    def meld(self, player_id: str) -> list[MeldUnit]:
        """Return the meld combinations recorded for ``player_id`` after the pass."""
        return list(self._meld.get(player_id, []))

    def meld_total(self, player_id: str) -> int:
        """Return the meld points recorded for ``player_id`` after the pass."""
        return sum(unit.points for unit in self._meld.get(player_id, []))

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
