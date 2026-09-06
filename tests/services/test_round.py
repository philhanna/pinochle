# tests.services.test_round
import pytest

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.meld import detect_meld
from pinochle.services.round import Round, RoundPhase

PLAYER_ORDER = ["N", "E", "S", "W"]


def round_at_passing(trump: Suit = Suit.SPADES) -> Round:
    """Return a dealt round advanced to the PASSING phase with ``trump`` named.

    ``E`` wins the auction at the minimum bid and names trump, which makes
    ``W`` the passing partner.
    """
    round_state = Round(dealer_id="N", player_order=PLAYER_ORDER)
    round_state.deal()
    round_state.place_bid("E", 250)
    for player_id in ("S", "W", "N"):
        round_state.place_bid(player_id, None)
    round_state.confirm_contract("E", accept=True)
    round_state.name_trump("E", trump)
    return round_state


def complete_exchange(round_state: Round) -> None:
    """Pass four cards each way, in whatever order the round requires."""
    while round_state.phase == RoundPhase.PASSING:
        passer = round_state.current_player
        round_state.pass_cards(passer, list(round_state.hand(passer))[:4])


def test_exchange_moves_round_to_melding():
    """Completing both passes should end the PASSING phase."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    assert round_state.phase == RoundPhase.MELDING


def test_meld_recorded_for_every_player():
    """Meld should be captured for all four players, not only the bidding team."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    for player_id in PLAYER_ORDER:
        assert round_state.meld(player_id) == detect_meld(
            list(round_state.hand(player_id)), round_state.trump
        )


def test_meld_survives_hands_being_emptied():
    """Recorded meld must not be recomputed once trick play empties the hands.

    This is the defect that made every meld score zero: the totals were read
    at scoring time, by which point no player held any cards.
    """
    round_state = round_at_passing()
    complete_exchange(round_state)
    recorded = {p: round_state.meld_total(p) for p in PLAYER_ORDER}

    for player_id in PLAYER_ORDER:
        hand = round_state.hand(player_id)
        hand.remove_many(list(hand))
        assert len(hand) == 0

    assert {p: round_state.meld_total(p) for p in PLAYER_ORDER} == recorded


def test_meld_is_never_combined_across_partners():
    """A team's meld is two independent detections, never one over 24 cards."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    combined = detect_meld(
        list(round_state.hand("E")) + list(round_state.hand("W")),
        round_state.trump,
    )
    separate = round_state.meld("E") + round_state.meld("W")
    assert sum(u.points for u in separate) <= sum(u.points for u in combined)


def test_cannot_play_before_meld_display_ends():
    """A lead during the meld hold is rejected; the phase must end first."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    card = list(round_state.hand("E"))[0]
    with pytest.raises(ValueError):
        round_state.play_card("E", card)


def test_begin_play_gives_lead_to_auction_winner():
    """Ending the meld display starts trick play with the bid winner leading."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    round_state.begin_play("E")
    assert round_state.phase == RoundPhase.PLAYING
    card = list(round_state.hand("E"))[0]
    assert round_state.play_card("E", card) is None


def test_only_the_auction_winner_ends_the_meld_display():
    """Nobody else can start play on the auction winner's behalf."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    with pytest.raises(ValueError):
        round_state.begin_play("W")
    with pytest.raises(ValueError):
        round_state.toss_in("N")


def test_tossing_in_skips_play_and_goes_straight_to_scoring():
    """Conceding ends the round without a card being played."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    round_state.toss_in("E")
    assert round_state.phase == RoundPhase.SCORING
    assert round_state.tossed_in is True
    assert round_state.tricks == []


def test_a_played_out_round_is_not_marked_tossed_in():
    """Choosing to play leaves the concession flag clear."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    round_state.begin_play("E")
    assert round_state.tossed_in is False


# ---------------------------------------------------------------------------
# Bidding outcomes
# ---------------------------------------------------------------------------

def dealt_round() -> Round:
    """Return a freshly dealt round sitting in the bidding phase."""
    round_state = Round(dealer_id="N", player_order=PLAYER_ORDER)
    round_state.deal()
    return round_state


def test_all_four_passing_abandons_the_round():
    """Nobody bidding throws the round in, with no contract to play (FR-31)."""
    round_state = dealt_round()
    for player_id in ("E", "S", "W", "N"):
        round_state.place_bid(player_id, None)
    assert round_state.phase == RoundPhase.ABANDONED
    assert round_state.bid_winner is None
    assert round_state.current_player is None


def test_lone_bidder_is_asked_to_confirm():
    """One bid and three passes offers the bidder a way out (FR-32)."""
    round_state = dealt_round()
    round_state.place_bid("E", 250)
    for player_id in ("S", "W", "N"):
        round_state.place_bid(player_id, None)
    assert round_state.phase == RoundPhase.CONFIRMING


def test_declining_a_lone_contract_abandons_the_round():
    """A declined contract leaves no bid winner and no contract."""
    round_state = dealt_round()
    round_state.place_bid("E", 250)
    for player_id in ("S", "W", "N"):
        round_state.place_bid(player_id, None)
    round_state.confirm_contract("E", accept=False)
    assert round_state.phase == RoundPhase.ABANDONED
    assert round_state.bid_winner is None
    assert round_state.contract is None


def test_contested_bidding_skips_confirmation():
    """Someone who was bid against is held to their contract."""
    round_state = dealt_round()
    round_state.place_bid("E", 250)
    round_state.place_bid("S", 260)
    round_state.place_bid("W", None)
    round_state.place_bid("N", None)
    round_state.place_bid("E", None)
    assert round_state.phase == RoundPhase.TRUMP
    assert round_state.bid_winner == "S"


def test_only_the_lone_bidder_may_confirm():
    """No other player can accept or decline on the bidder's behalf."""
    round_state = dealt_round()
    round_state.place_bid("E", 250)
    for player_id in ("S", "W", "N"):
        round_state.place_bid(player_id, None)
    with pytest.raises(ValueError):
        round_state.confirm_contract("W", accept=True)


# ---------------------------------------------------------------------------
# Turn state
# ---------------------------------------------------------------------------

def test_current_player_through_the_phases():
    """Every phase that expects a player names one; the rest name nobody."""
    round_state = Round(dealer_id="N", player_order=PLAYER_ORDER)
    assert round_state.current_player is None          # DEALING

    round_state.deal()
    assert round_state.current_player == "E"           # BIDDING, left of dealer

    round_state.place_bid("E", 250)
    for player_id in ("S", "W", "N"):
        round_state.place_bid(player_id, None)
    assert round_state.phase == RoundPhase.CONFIRMING  # E bid alone
    assert round_state.current_player == "E"

    round_state.confirm_contract("E", accept=True)
    assert round_state.current_player == "E"           # TRUMP, the bid winner

    round_state.name_trump("E", Suit.SPADES)
    assert round_state.current_player == "W"           # PASSING, partner first

    round_state.pass_cards("W", list(round_state.hand("W"))[:4])
    assert round_state.current_player == "E"           # PASSING, winner returns

    round_state.pass_cards("E", list(round_state.hand("E"))[:4])
    assert round_state.current_player == "E"           # MELDING, winner decides

    round_state.begin_play("E")
    assert round_state.current_player == "E"           # PLAYING, winner leads


def test_current_player_walks_clockwise_within_a_trick():
    """Each card played hands the turn to the next seat."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    round_state.begin_play("E")

    expected = ["E", "S", "W", "N"]
    for player_id in expected:
        assert round_state.current_player == player_id
        round_state.play_card(player_id, round_state.legal_plays(player_id)[0])

    # The completed trick sits on the table; nobody is on the clock until it
    # is swept, and the next lead is refused meanwhile.
    assert round_state.trick_pending is True
    assert round_state.current_player is None
    with pytest.raises(ValueError):
        round_state.play_card("E", list(round_state.hand("E"))[0])

    round_state.clear_trick()
    assert round_state.trick_pending is False
    assert round_state.current_player in expected
    assert len(round_state.tricks) == 1


def test_play_out_of_turn_is_rejected():
    """A player may not play before the turn reaches them."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    round_state.begin_play("E")
    with pytest.raises(ValueError):
        round_state.play_card("S", round_state.legal_plays("S")[0])


def test_illegal_play_is_rejected():
    """A card outside the legal set must be refused even though it is held.

    ``S`` is dealt a hand that can follow the lead, so the off-suit card is
    unambiguously illegal regardless of what the shuffle produced.
    """
    round_state = round_at_passing(Suit.SPADES)
    complete_exchange(round_state)
    round_state.begin_play("E")

    lead = round_state.legal_plays("E")[0]
    round_state.play_card("E", lead)

    off_suit = next(s for s in Suit if s not in (lead.suit, Suit.SPADES))
    discard = Card(Rank.ACE, off_suit)
    hand = round_state.hand("S")
    hand.remove_many(list(hand))
    hand.add([Card(Rank.NINE, lead.suit), discard])

    assert discard not in round_state.legal_plays("S")
    with pytest.raises(ValueError):
        round_state.play_card("S", discard)
