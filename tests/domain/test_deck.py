# tests.domain.test_deck
import pytest

from pinochle.domain.cards import Card, Deck, Rank, Suit


def test_deck_has_48_cards():
    assert len(Deck()) == 48


def test_deck_has_two_of_each_card():
    deck = Deck()
    cards = list(deck)
    for suit in Suit:
        for rank in Rank:
            count = sum(1 for c in cards if c.rank == rank and c.suit == suit)
            assert count == 2, f"Expected 2 of {rank} {suit}, got {count}"


def test_shuffle_changes_order():
    deck = Deck()
    original = list(deck)
    deck.shuffle()
    shuffled = list(deck)
    # With 48 cards, the probability of identical order after shuffle is negligible
    assert shuffled != original


def test_deal_removes_cards():
    deck = Deck()
    hand = deck.deal(12)
    assert len(hand) == 12
    assert len(deck) == 36


def test_deal_returns_cards():
    deck = Deck()
    hand = deck.deal(12)
    assert all(isinstance(c, Card) for c in hand)


def test_deal_raises_when_insufficient():
    deck = Deck()
    with pytest.raises(ValueError):
        deck.deal(49)
