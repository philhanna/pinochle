# tests.domain.test_bid
import pytest

from pinochle.domain.bid import BiddingRound, is_valid_bid, MINIMUM_BID


PLAYERS = ["N", "E", "S", "W"]


def test_valid_bid_above_minimum():
    """A bid at the minimum opening threshold should be accepted."""
    assert is_valid_bid(250, 0) is True


def test_valid_bid_increments():
    """A higher bid in ten-point increments should be accepted."""
    assert is_valid_bid(260, 250) is True


def test_invalid_bid_not_multiple_of_10():
    """Bids that do not follow the increment rule should be rejected."""
    assert is_valid_bid(255, 0) is False


def test_invalid_bid_below_minimum():
    """Bids below the minimum opening amount should be rejected."""
    assert is_valid_bid(240, 0) is False


def test_invalid_bid_not_above_current():
    """A bid must exceed the current high bid to be valid."""
    assert is_valid_bid(250, 250) is False


def test_pass_removes_player():
    """Passing should remove the player from the active bidder list."""
    b = BiddingRound(PLAYERS)
    b.place_bid("N", None)
    assert "N" not in b.active_players


def test_bidding_ends_when_three_pass():
    """Bidding should end once only one active bidder remains."""
    b = BiddingRound(PLAYERS)
    b.place_bid("N", 250)
    b.place_bid("E", None)
    b.place_bid("S", None)
    b.place_bid("W", None)
    assert b.is_over
    assert b.high_bidder == "N"
    assert b.current_high == 250


def test_current_bidder_starts_at_the_head_of_the_order():
    """The first player in the order opens the bidding."""
    assert BiddingRound(PLAYERS).current_bidder == "N"


def test_current_bidder_advances_clockwise():
    """Each bid or pass moves the turn to the next player."""
    b = BiddingRound(PLAYERS)
    b.place_bid("N", 250)
    assert b.current_bidder == "E"
    b.place_bid("E", None)
    assert b.current_bidder == "S"


def test_current_bidder_skips_players_who_passed():
    """A player who has passed is not offered another turn."""
    b = BiddingRound(PLAYERS)
    b.place_bid("N", 250)
    b.place_bid("E", None)
    b.place_bid("S", 260)
    b.place_bid("W", None)
    assert b.current_bidder == "N"


def test_last_player_still_gets_a_turn_after_three_passes():
    """Three passes with no bid must not end the auction over the fourth's head."""
    b = BiddingRound(PLAYERS)
    for player_id in ("N", "E", "S"):
        b.place_bid(player_id, None)
    assert not b.is_over
    assert b.current_bidder == "W"


def test_last_player_may_open_after_three_passes():
    """The last active player can still open the bidding."""
    b = BiddingRound(PLAYERS)
    for player_id in ("N", "E", "S"):
        b.place_bid(player_id, None)
    b.place_bid("W", 250)
    assert b.is_over
    assert b.high_bidder == "W"


def test_everyone_passing_ends_with_no_bidder():
    """All four passing leaves nobody holding a contract."""
    b = BiddingRound(PLAYERS)
    for player_id in PLAYERS:
        b.place_bid(player_id, None)
    assert b.is_over
    assert b.high_bidder is None
    assert b.bid_count == 0


def test_current_bidder_is_none_once_over():
    """Bidding that has ended has nobody on the clock."""
    b = BiddingRound(PLAYERS)
    b.place_bid("N", 250)
    for player_id in ("E", "S", "W"):
        b.place_bid(player_id, None)
    assert b.current_bidder is None


def test_bid_out_of_turn_is_rejected():
    """Bidding before your turn comes round must be refused."""
    b = BiddingRound(PLAYERS)
    with pytest.raises(ValueError):
        b.place_bid("S", 250)


def test_out_of_turn_bid_leaves_state_untouched():
    """A rejected bid must not change the high bid or the turn."""
    b = BiddingRound(PLAYERS)
    b.place_bid("N", 250)
    with pytest.raises(ValueError):
        b.place_bid("W", 300)
    assert b.current_high == 250
    assert b.current_bidder == "E"


def test_bid_raises_on_invalid_amount():
    """An invalid numeric bid should raise ``ValueError``."""
    b = BiddingRound(PLAYERS)
    with pytest.raises(ValueError):
        b.place_bid("N", 245)


def test_bid_raises_after_pass():
    """A player who has passed should not be allowed to bid again."""
    b = BiddingRound(PLAYERS)
    b.place_bid("N", None)
    with pytest.raises(ValueError):
        b.place_bid("N", 250)


def test_bid_raises_when_over():
    """No additional bids should be accepted after bidding is complete."""
    b = BiddingRound(PLAYERS)
    b.place_bid("N", 250)
    b.place_bid("E", None)
    b.place_bid("S", None)
    b.place_bid("W", None)
    with pytest.raises(ValueError):
        b.place_bid("N", 260)
