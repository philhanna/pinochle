# tests.web.test_event_encoder
import json

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.game import (
    CardPlayed,
    DealerSelected,
    DrawMade,
    HoldBegun,
    HoldEnded,
    TrumpNamed,
)
from pinochle.domain.hold import HoldReason
from pinochle.domain.trick import TrickPlay
from pinochle.domain.game import TrickCompleted
from pinochle.web.event_encoder import encode_event
from pinochle.web.transport_events import GameAbandoned, SeatLost, SeatRejoined

TURN = {"phase": "PLAYING", "current_player_id": "N", "paused": None, "round_number": 1}


def test_frame_has_id_event_and_data_lines():
    """The frame shape follows design.md §6.4 exactly."""
    event = DealerSelected(game_id="g1", dealer_player_id="N")
    frame = encode_event(event, seq=42, turn=TURN)
    assert frame == (
        'id: 42\n'
        'event: dealer_selected\n'
        f'data: {json.dumps({"seq": 42, "type": "dealer_selected", "turn": TURN, "payload": {"dealer_player_id": "N"}})}\n'
        '\n'
    )


def test_ids_reflect_the_sequence_number_passed_in():
    """Consecutive calls with increasing seq numbers should produce increasing ids."""
    event = DealerSelected(game_id="g1", dealer_player_id="N")
    first = encode_event(event, seq=1, turn=TURN)
    second = encode_event(event, seq=2, turn=TURN)
    assert first.startswith("id: 1\n")
    assert second.startswith("id: 2\n")


def test_card_fields_use_the_wire_codec():
    """A card embedded in an event must be encoded to its two-character code."""
    event = DrawMade(game_id="g1", player_id="N", position=3, card=Card(Rank.TEN, Suit.SPADES))
    frame = encode_event(event, seq=1, turn=TURN)
    payload = _payload_of(frame)
    assert payload["card"] == "TS"


def test_suit_fields_use_the_wire_codec():
    """A suit embedded in an event must be encoded to its wire name."""
    event = TrumpNamed(game_id="g1", suit=Suit.HEARTS)
    frame = encode_event(event, seq=1, turn=TURN)
    assert _payload_of(frame)["suit"] == "HEARTS"


def test_trick_completed_pairs_each_card_with_its_player():
    """design.md §6.5: trick_completed carries {player_id, card} pairs."""
    event = TrickCompleted(
        game_id="g1",
        winner_player_id="S",
        plays=[
            TrickPlay("N", Card(Rank.ACE, Suit.SPADES)),
            TrickPlay("E", Card(Rank.NINE, Suit.SPADES)),
            TrickPlay("S", Card(Rank.KING, Suit.SPADES)),
            TrickPlay("W", Card(Rank.QUEEN, Suit.SPADES)),
        ],
    )
    frame = encode_event(event, seq=1, turn=TURN)
    payload = _payload_of(frame)
    assert payload["cards"] == [
        {"player_id": "N", "card": "AS"},
        {"player_id": "E", "card": "9S"},
        {"player_id": "S", "card": "KS"},
        {"player_id": "W", "card": "QS"},
    ]


def test_a_newline_embedded_in_a_field_does_not_split_the_frame():
    """A player name with a newline must not be able to forge a second frame."""
    event = CardPlayed(game_id="g1", player_id="N\nevent: forged", card=Card(Rank.ACE, Suit.SPADES))
    frame = encode_event(event, seq=1, turn=TURN)
    lines = frame.split("\n")
    # Exactly three content lines (id, event, data) plus the trailing blanks.
    assert lines[0].startswith("id: ")
    assert lines[1] == "event: card_played"
    assert lines[2].startswith("data: ")
    assert lines[3:] == ["", ""]


def test_transport_level_events_encode_too():
    """RT-12: seat_lost, seat_rejoined, and game_abandoned aren't domain events
    but still need frames (design.md §14.3)."""
    assert _payload_of(encode_event(SeatLost(game_id="g1", player_id="N"), 1, TURN)) == {
        "player_id": "N",
    }
    assert _payload_of(encode_event(SeatRejoined(game_id="g1", player_id="N"), 1, TURN)) == {
        "player_id": "N",
    }
    assert _payload_of(encode_event(GameAbandoned(game_id="g1", reason="seat lost"), 1, TURN)) == {
        "reason": "seat lost",
    }


def _payload_of(frame: str) -> dict:
    """Pull the JSON payload dict out of an encoded frame, for assertions."""
    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    return json.loads(data_line[len("data: "):])["payload"]


def test_hold_begun_names_the_hold_and_how_it_ends():
    """RT-13: a client has to tell a timed pause from one it may release."""
    event = HoldBegun(
        game_id="g1", hold_id=7, reason=HoldReason.ROUND_SCORED,
        seconds=None, ackable=True,
    )
    _, payload = payload_of(encode_event(event, seq=9, turn=TURN))
    assert payload == {
        "hold_id": 7, "reason": "round_scored", "seconds": None, "ackable": True,
    }


def test_hold_ended_names_the_hold_that_ended():
    """The closing half of RT-10's delimiting pair."""
    event = HoldEnded(game_id="g1", hold_id=7, reason=HoldReason.ROUND_SCORED)
    name, payload = payload_of(encode_event(event, seq=10, turn=TURN))
    assert name == "hold_ended"
    assert payload == {"hold_id": 7, "reason": "round_scored"}


def test_a_hold_reason_crosses_the_wire_in_snake_case():
    """The client switches on this string, so its spelling is the contract."""
    event = HoldBegun(
        game_id="g1", hold_id=1, reason=HoldReason.TRICK_CLEAR,
        seconds=1.5, ackable=False,
    )
    _, payload = payload_of(encode_event(event, seq=1, turn=TURN))
    assert payload["reason"] == "trick_clear"
    assert payload["seconds"] == 1.5


def payload_of(frame: str) -> tuple[str, dict]:
    """Return the frame's event name and decoded payload."""
    data = json.loads(frame.split("data: ", 1)[1].split("\n", 1)[0])
    return data["type"], data["payload"]
