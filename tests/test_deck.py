from pinochle import Deck


def test_cards():
    deck = Deck()
    assert 48 == len(deck.cards)


def test_shuffle():
    deck = Deck()
    deck.shuffle()
    assert 48 == len(deck.cards)

