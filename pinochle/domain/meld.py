# pinochle.domain.meld
from dataclasses import dataclass
from collections import Counter

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit


@dataclass
class MeldUnit:
    """A single recognized meld combination and the points it scores.

    Attributes:
        name: Human-readable meld name (e.g. ``"Run"``, ``"Double Pinochle"``,
            ``"100 Aces"``).
        points: Point value awarded for this meld combination.
    """

    name: str
    points: int


def _count(cards: list[Card], rank: Rank, suit: Suit) -> int:
    """Count copies of a specific rank and suit in ``cards``."""
    return sum(1 for c in cards if c.rank == rank and c.suit == suit)


def detect_meld(cards: list[Card], trump: Suit) -> list[MeldUnit]:
    """Return all meld units detectable in `cards` given `trump`."""
    units: list[MeldUnit] = []

    # --- Runs ---
    run_cards = [Rank.ACE, Rank.TEN, Rank.KING, Rank.QUEEN, Rank.JACK]
    single_run_count = min(_count(cards, r, trump) for r in run_cards)
    if single_run_count >= 2:
        units.append(MeldUnit("Double Run", 1500))
    elif single_run_count == 1:
        units.append(MeldUnit("Run", 150))

    # --- Marriages ---
    for suit in Suit:
        pairs = min(_count(cards, Rank.KING, suit), _count(cards, Rank.QUEEN, suit))
        if suit == trump:
            # Each run consumes one trump King and Queen; only spare pairs meld.
            pairs -= single_run_count
        if pairs >= 1:
            name = "Royal Marriage" if suit == trump else "Marriage"
            points = 40 if suit == trump else 20
            units.append(MeldUnit(name, points * pairs))

    # --- Pinochle (Q♠ + J♦) ---
    pinochle_count = min(
        _count(cards, Rank.QUEEN, Suit.SPADES),
        _count(cards, Rank.JACK, Suit.DIAMONDS),
    )
    if pinochle_count >= 2:
        units.append(MeldUnit("Double Pinochle", 300))
    elif pinochle_count == 1:
        units.append(MeldUnit("Pinochle", 40))

    # --- Aces around ---
    aces = min(_count(cards, Rank.ACE, s) for s in Suit)
    if aces >= 2:
        units.append(MeldUnit("1000 Aces", 1000))
    elif aces == 1:
        units.append(MeldUnit("100 Aces", 100))

    # --- Kings around ---
    kings = min(_count(cards, Rank.KING, s) for s in Suit)
    if kings >= 2:
        units.append(MeldUnit("800 Kings", 800))
    elif kings == 1:
        units.append(MeldUnit("80 Kings", 80))

    # --- Queens around ---
    queens = min(_count(cards, Rank.QUEEN, s) for s in Suit)
    if queens >= 2:
        units.append(MeldUnit("600 Queens", 600))
    elif queens == 1:
        units.append(MeldUnit("60 Queens", 60))

    # --- Jacks around ---
    jacks = min(_count(cards, Rank.JACK, s) for s in Suit)
    if jacks >= 2:
        units.append(MeldUnit("400 Jacks", 400))
    elif jacks == 1:
        units.append(MeldUnit("40 Jacks", 40))

    # --- Trump nine ---
    nines = _count(cards, Rank.NINE, trump)
    if nines >= 1:
        units.append(MeldUnit("Trump Nine", 10 * nines))

    return units


def total_meld(cards: list[Card], trump: Suit) -> int:
    """Return the total meld points available in ``cards``."""
    return sum(u.points for u in detect_meld(cards, trump))
