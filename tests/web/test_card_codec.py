# tests.web.test_card_codec
import pytest

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.web.card_codec import decode_card, decode_suit, encode_card, encode_suit


def test_encode_card_uses_a_two_character_wire_code():
    """Ten encodes as ``T``, not the domain's two-character ``"10"``."""
    assert encode_card(Card(Rank.TEN, Suit.SPADES)) == "TS"
    assert encode_card(Card(Rank.NINE, Suit.CLUBS)) == "9C"
    assert encode_card(Card(Rank.JACK, Suit.DIAMONDS)) == "JD"
    assert encode_card(Card(Rank.QUEEN, Suit.HEARTS)) == "QH"
    assert encode_card(Card(Rank.KING, Suit.SPADES)) == "KS"
    assert encode_card(Card(Rank.ACE, Suit.SPADES)) == "AS"


def test_decode_card_round_trips():
    """Decoding a wire code should return the matching card."""
    assert decode_card("TS") == Card(Rank.TEN, Suit.SPADES)
    assert decode_card("9C") == Card(Rank.NINE, Suit.CLUBS)
    assert decode_card("AS") == Card(Rank.ACE, Suit.SPADES)


def test_round_trip_every_card_in_a_fresh_deck():
    """Every rank/suit combination should encode and decode without loss."""
    for rank in Rank:
        for suit in Suit:
            card = Card(rank, suit)
            assert decode_card(encode_card(card)) == card


def test_suit_wire_format_is_platform_independent():
    """Suit codes must not depend on Suit.__str__'s platform branching."""
    assert encode_suit(Suit.SPADES) == "SPADES"
    assert encode_suit(Suit.HEARTS) == "HEARTS"
    assert decode_suit("DIAMONDS") == Suit.DIAMONDS
    assert decode_suit("CLUBS") == Suit.CLUBS


def test_decode_card_rejects_a_malformed_code():
    """An unparseable code should raise ValueError, not a bare KeyError (§5.5)."""
    with pytest.raises(ValueError):
        decode_card("ZZ")
    with pytest.raises(ValueError):
        decode_card("")


def test_decode_suit_rejects_an_unknown_name():
    """An unparseable suit name should raise ValueError, not a bare KeyError (§5.5)."""
    with pytest.raises(ValueError):
        decode_suit("NOT_A_SUIT")
