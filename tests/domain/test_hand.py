# tests.domain.test_hand
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.hand import Hand
from pinochle.domain.trick import Trick

TRUMP = Suit.SPADES


def card(rank: Rank, suit: Suit) -> Card:
    """Shorthand for building a card."""
    return Card(rank, suit)


def trick_of(*cards: Card) -> Trick:
    """Return a trick with ``cards`` already played, led by the first."""
    t = Trick(lead_player_id="lead", trump=TRUMP)
    for index, c in enumerate(cards):
        t.play(f"p{index}", c)
    return t


def test_leading_allows_any_card():
    """With no trick in progress every card is legal."""
    hand = Hand([card(Rank.NINE, Suit.HEARTS), card(Rank.ACE, Suit.CLUBS)])
    assert len(hand.legal_plays(None, TRUMP)) == 2


def test_must_follow_suit():
    """Holding the led suit restricts play to that suit."""
    hand = Hand([
        card(Rank.NINE, Suit.HEARTS),
        card(Rank.KING, Suit.HEARTS),
        card(Rank.ACE, Suit.CLUBS),
    ])
    legal = hand.legal_plays(trick_of(card(Rank.JACK, Suit.HEARTS)), TRUMP)
    assert all(c.suit == Suit.HEARTS for c in legal)


def test_need_not_beat_a_non_trump_led_suit():
    """Following a non-trump lead, any card of the led suit will do."""
    hand = Hand([
        card(Rank.NINE, Suit.HEARTS),
        card(Rank.ACE, Suit.HEARTS),
        card(Rank.TEN, Suit.HEARTS),
    ])
    legal = hand.legal_plays(trick_of(card(Rank.KING, Suit.HEARTS)), TRUMP)
    assert len(legal) == 3


def test_may_play_low_when_unable_to_beat():
    """Holding nothing higher, any card of the led suit will do."""
    hand = Hand([card(Rank.NINE, Suit.HEARTS), card(Rank.JACK, Suit.HEARTS)])
    legal = hand.legal_plays(trick_of(card(Rank.ACE, Suit.HEARTS)), TRUMP)
    assert len(legal) == 2


def test_void_in_led_suit_must_trump():
    """A player void in the led suit must play trump if they hold any."""
    hand = Hand([card(Rank.NINE, TRUMP), card(Rank.ACE, Suit.CLUBS)])
    legal = hand.legal_plays(trick_of(card(Rank.KING, Suit.HEARTS)), TRUMP)
    assert legal == [card(Rank.NINE, TRUMP)]


def test_must_overtrump_when_able():
    """A trump already played must be beaten if the hand can beat it."""
    hand = Hand([
        card(Rank.NINE, TRUMP),
        card(Rank.ACE, TRUMP),
        card(Rank.TEN, Suit.CLUBS),
    ])
    trick = trick_of(card(Rank.KING, Suit.HEARTS), card(Rank.QUEEN, TRUMP))
    assert hand.legal_plays(trick, TRUMP) == [card(Rank.ACE, TRUMP)]


def test_may_undertrump_when_unable_to_overtrump():
    """Holding only lower trump, any trump is acceptable."""
    hand = Hand([card(Rank.NINE, TRUMP), card(Rank.TEN, Suit.CLUBS)])
    trick = trick_of(card(Rank.KING, Suit.HEARTS), card(Rank.ACE, TRUMP))
    assert hand.legal_plays(trick, TRUMP) == [card(Rank.NINE, TRUMP)]


def test_void_in_both_may_discard_anything():
    """With neither the led suit nor trump, any card may be discarded."""
    hand = Hand([card(Rank.NINE, Suit.CLUBS), card(Rank.ACE, Suit.DIAMONDS)])
    legal = hand.legal_plays(trick_of(card(Rank.KING, Suit.HEARTS)), TRUMP)
    assert len(legal) == 2


def test_trump_led_requires_beating_the_highest_trump():
    """When trump is led the follow-suit and overtrump rules coincide."""
    hand = Hand([card(Rank.NINE, TRUMP), card(Rank.ACE, TRUMP)])
    assert hand.legal_plays(trick_of(card(Rank.KING, TRUMP)), TRUMP) == [
        card(Rank.ACE, TRUMP)
    ]


def test_may_undertrump_a_trump_lead_when_unable_to_beat():
    """Holding no higher trump, any trump may follow a trump lead."""
    hand = Hand([card(Rank.NINE, TRUMP), card(Rank.JACK, TRUMP)])
    assert len(hand.legal_plays(trick_of(card(Rank.ACE, TRUMP)), TRUMP)) == 2


def test_led_suit_beaten_by_trump_allows_any_led_suit_card():
    """Following a plain suit that has been trumped, any led-suit card will do."""
    hand = Hand([card(Rank.NINE, Suit.HEARTS), card(Rank.ACE, Suit.HEARTS)])
    trick = trick_of(card(Rank.KING, Suit.HEARTS), card(Rank.NINE, TRUMP))
    assert len(hand.legal_plays(trick, TRUMP)) == 2
