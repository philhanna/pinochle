# pinochle.domain.meld
from dataclasses import dataclass, field
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
    cards: list[Card] = field(default_factory=list)


def _take(
    cards: list[Card], requirements: Counter[tuple[Rank, Suit]],
) -> list[Card]:
    """Pick the physical cards that make one displayed meld combination."""
    remaining = requirements.copy()
    selected: list[Card] = []
    for card in cards:
        key = (card.rank, card.suit)
        if remaining[key] > 0:
            selected.append(card)
            remaining[key] -= 1
    return selected


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
        units.append(MeldUnit(
            "Double Run", 1500,
            _take(cards, Counter({(rank, trump): 2 for rank in run_cards})),
        ))
    elif single_run_count == 1:
        units.append(MeldUnit(
            "Run", 150,
            _take(cards, Counter({(rank, trump): 1 for rank in run_cards})),
        ))

    # --- Marriages ---
    for suit in Suit:
        pairs = min(_count(cards, Rank.KING, suit), _count(cards, Rank.QUEEN, suit))
        if suit == trump:
            # Each run consumes one trump King and Queen; only spare pairs meld.
            pairs -= single_run_count
        if pairs >= 1:
            name = "Royal Marriage" if suit == trump else "Marriage"
            points = 40 if suit == trump else 20
            units.append(MeldUnit(
                name, points * pairs,
                _take(cards, Counter({
                    (Rank.KING, suit): pairs,
                    (Rank.QUEEN, suit): pairs,
                })),
            ))

    # --- Pinochle (Q♠ + J♦) ---
    pinochle_count = min(
        _count(cards, Rank.QUEEN, Suit.SPADES),
        _count(cards, Rank.JACK, Suit.DIAMONDS),
    )
    if pinochle_count >= 2:
        units.append(MeldUnit(
            "Double Pinochle", 300,
            _take(cards, Counter({
                (Rank.QUEEN, Suit.SPADES): 2,
                (Rank.JACK, Suit.DIAMONDS): 2,
            })),
        ))
    elif pinochle_count == 1:
        units.append(MeldUnit(
            "Pinochle", 40,
            _take(cards, Counter({
                (Rank.QUEEN, Suit.SPADES): 1,
                (Rank.JACK, Suit.DIAMONDS): 1,
            })),
        ))

    # --- Aces around ---
    aces = min(_count(cards, Rank.ACE, s) for s in Suit)
    if aces >= 2:
        units.append(MeldUnit(
            "1000 Aces", 1000,
            _take(cards, Counter({(Rank.ACE, suit): 2 for suit in Suit})),
        ))
    elif aces == 1:
        units.append(MeldUnit(
            "100 Aces", 100,
            _take(cards, Counter({(Rank.ACE, suit): 1 for suit in Suit})),
        ))

    # --- Kings around ---
    kings = min(_count(cards, Rank.KING, s) for s in Suit)
    if kings >= 2:
        units.append(MeldUnit(
            "800 Kings", 800,
            _take(cards, Counter({(Rank.KING, suit): 2 for suit in Suit})),
        ))
    elif kings == 1:
        units.append(MeldUnit(
            "80 Kings", 80,
            _take(cards, Counter({(Rank.KING, suit): 1 for suit in Suit})),
        ))

    # --- Queens around ---
    queens = min(_count(cards, Rank.QUEEN, s) for s in Suit)
    if queens >= 2:
        units.append(MeldUnit(
            "600 Queens", 600,
            _take(cards, Counter({(Rank.QUEEN, suit): 2 for suit in Suit})),
        ))
    elif queens == 1:
        units.append(MeldUnit(
            "60 Queens", 60,
            _take(cards, Counter({(Rank.QUEEN, suit): 1 for suit in Suit})),
        ))

    # --- Jacks around ---
    jacks = min(_count(cards, Rank.JACK, s) for s in Suit)
    if jacks >= 2:
        units.append(MeldUnit(
            "400 Jacks", 400,
            _take(cards, Counter({(Rank.JACK, suit): 2 for suit in Suit})),
        ))
    elif jacks == 1:
        units.append(MeldUnit(
            "40 Jacks", 40,
            _take(cards, Counter({(Rank.JACK, suit): 1 for suit in Suit})),
        ))

    # --- Trump nine ---
    nines = _count(cards, Rank.NINE, trump)
    if nines >= 1:
        units.append(MeldUnit(
            "Trump Nine", 10 * nines,
            _take(cards, Counter({(Rank.NINE, trump): nines})),
        ))

    return units


def total_meld(cards: list[Card], trump: Suit) -> int:
    """Return the total meld points available in ``cards``."""
    return sum(u.points for u in detect_meld(cards, trump))


def cards_in_meld(cards: list[Card], trump: Suit) -> list[Card]:
    """Return the physical cards a player lays face-up for their meld.

    A card can support several combinations at once — the queen of spades can
    be both part of queens around and a pinochle — but is laid down only once.
    Duplicate cards are retained when a double combination actually needs
    both physical copies.
    """
    held = Counter((card.rank, card.suit) for card in cards)
    needed: Counter[tuple[Rank, Suit]] = Counter()

    def require(rank: Rank, suit: Suit, count: int) -> None:
        key = (rank, suit)
        needed[key] = max(needed[key], count)

    run_ranks = [Rank.ACE, Rank.TEN, Rank.KING, Rank.QUEEN, Rank.JACK]
    runs = min(held[(rank, trump)] for rank in run_ranks)
    for rank in run_ranks:
        require(rank, trump, runs)

    for suit in Suit:
        pairs = min(held[(Rank.KING, suit)], held[(Rank.QUEEN, suit)])
        require(Rank.KING, suit, pairs)
        require(Rank.QUEEN, suit, pairs)

    pinochles = min(
        held[(Rank.QUEEN, Suit.SPADES)], held[(Rank.JACK, Suit.DIAMONDS)],
    )
    require(Rank.QUEEN, Suit.SPADES, pinochles)
    require(Rank.JACK, Suit.DIAMONDS, pinochles)

    for rank in (Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK):
        around = min(held[(rank, suit)] for suit in Suit)
        for suit in Suit:
            require(rank, suit, around)

    require(Rank.NINE, trump, held[(Rank.NINE, trump)])

    remaining = needed.copy()
    exposed: list[Card] = []
    for card in cards:
        key = (card.rank, card.suit)
        if remaining[key] > 0:
            exposed.append(card)
            remaining[key] -= 1
    return exposed
