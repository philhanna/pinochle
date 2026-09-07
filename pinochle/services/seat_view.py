# pinochle.services.seat_view
from dataclasses import dataclass

from pinochle.domain.bid import BidEntry
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit
from pinochle.domain.meld import MeldUnit


@dataclass(frozen=True)
class SeatView:
    """The slice of a round one seat is entitled to see (FR-74).

    Built by ``ComputerDriver`` and handed to the strategy, which is never
    given the ``Game`` or ``Round`` directly — it cannot read another seat's
    hand because nothing in its input carries one.

    Attributes:
        player_id: The seat this view belongs to.
        hand: The seat's own cards.
        bid_history: Every bid and pass made so far in the auction.
        current_high_bid: The high bid standing, or 0 if none has been made.
        trump: The trump suit, once named; ``None`` before then.
        cards_on_table: The cards played into the trick in progress so far.
        exposed_meld: Every player's recorded meld, once exposed after the
            pass — meld is public at a real table, so this is not limited
            to the seat's own.
        legal_plays: The cards this seat may legally play right now.
    """

    player_id: str
    hand: list[Card]
    bid_history: list[BidEntry]
    current_high_bid: int
    trump: Suit | None
    cards_on_table: list[Card]
    exposed_meld: dict[str, list[MeldUnit]]
    legal_plays: list[Card]
