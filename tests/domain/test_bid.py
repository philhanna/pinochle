# tests.domain.test_bid
import pytest

from pinochle.domain.bid import BiddingRound, is_valid_bid, MINIMUM_BID


PLAYERS = ["N", "E", "S", "W"]


def test_valid_bid_above_minimum():
    assert is_valid_bid(250, 0) is True


def test_valid_bid_increments():
    assert is_valid_bid(260, 250) is True


def test_invalid_bid_not_multiple_of_10():
    assert is_valid_bid(255, 0) is False


def test_invalid_bid_below_minimum():
    assert is_valid_bid(240, 0) is False


def test_invalid_bid_not_above_current():
    assert is_valid_bid(250, 250) is False


def test_pass_removes_player():
    b = BiddingRound(PLAYERS)
    b.place_bid("N", None)
    assert "N" not in b.active_players


def test_bidding_ends_when_three_pass():
    b = BiddingRound(PLAYERS)
    b.place_bid("N", 250)
    b.place_bid("E", None)
    b.place_bid("S", None)
    b.place_bid("W", None)
    assert b.is_over
    assert b.high_bidder == "N"
    assert b.current_high == 250


def test_bid_raises_on_invalid_amount():
    b = BiddingRound(PLAYERS)
    with pytest.raises(ValueError):
        b.place_bid("N", 245)


def test_bid_raises_after_pass():
    b = BiddingRound(PLAYERS)
    b.place_bid("N", None)
    with pytest.raises(ValueError):
        b.place_bid("N", 250)


def test_bid_raises_when_over():
    b = BiddingRound(PLAYERS)
    b.place_bid("N", 250)
    b.place_bid("E", None)
    b.place_bid("S", None)
    b.place_bid("W", None)
    with pytest.raises(ValueError):
        b.place_bid("N", 260)
