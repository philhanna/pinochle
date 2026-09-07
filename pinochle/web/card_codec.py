# pinochle.web.card_codec
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit

# The wire format's rank letter is its own table, distinct from
# Rank.short_name ("10" for TEN): the wire format is a fixed two characters,
# so ten is "T" (design.md §5.1 — "TS" is the ten of spades).
_RANK_TO_WIRE = {
    Rank.NINE: "9",
    Rank.JACK: "J",
    Rank.QUEEN: "Q",
    Rank.KING: "K",
    Rank.TEN: "T",
    Rank.ACE: "A",
}
_WIRE_TO_RANK = {v: k for k, v in _RANK_TO_WIRE.items()}

# Suit.character is already the ASCII S/H/D/C letter and, unlike
# Suit.__str__, does not vary by platform, so the wire format reuses it
# directly rather than defining a second suit table.
_WIRE_TO_SUIT = {suit.character: suit for suit in Suit}


def encode_card(card: Card) -> str:
    """Return the two-character wire code for ``card`` (e.g. ``"TS"``)."""
    return _RANK_TO_WIRE[card.rank] + card.suit.character


def decode_card(code: str) -> Card:
    """Return the ``Card`` named by a two-character wire code.

    Raises ``ValueError`` for anything that isn't one, so a malformed card
    code from a client maps to the same 422 a pydantic validation failure
    would (design.md §5.5) rather than an unhandled lookup error.
    """
    rank_letter, suit_letter = code[:1], code[1:]
    try:
        return Card(_WIRE_TO_RANK[rank_letter], _WIRE_TO_SUIT[suit_letter])
    except KeyError:
        raise ValueError(f"{code!r} is not a valid card code.") from None


def encode_suit(suit: Suit) -> str:
    """Return the wire name for ``suit`` (e.g. ``"SPADES"``)."""
    return suit.name


def decode_suit(name: str) -> Suit:
    """Return the ``Suit`` named by its wire name (e.g. ``"SPADES"``).

    Raises ``ValueError`` for anything else, for the same reason as
    ``decode_card``.
    """
    try:
        return Suit[name]
    except KeyError:
        raise ValueError(f"{name!r} is not a valid suit name.") from None
