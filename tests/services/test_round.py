# tests.services.test_round
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
    round_state.name_trump("E", trump)
    return round_state


def complete_exchange(round_state: Round) -> None:
    """Pass four cards each way between the auction winner and their partner."""
    for player_id in ("E", "W"):
        round_state.pass_cards(player_id, list(round_state.hand(player_id))[:4])


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
    try:
        round_state.play_card("E", card)
    except ValueError:
        pass
    else:
        raise AssertionError("play_card should be rejected during MELDING")


def test_advance_to_playing_gives_lead_to_auction_winner():
    """Ending the meld display starts trick play with the bid winner leading."""
    round_state = round_at_passing()
    complete_exchange(round_state)
    round_state.advance_to_playing()
    assert round_state.phase == RoundPhase.PLAYING
    card = list(round_state.hand("E"))[0]
    assert round_state.play_card("E", card) is None
