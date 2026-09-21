# pinochle.web.event_encoder
import json

from pinochle.domain.game import (
    BidPlaced,
    CardPlayed,
    CardsDealt,
    CardsPassed,
    ContractOffered,
    ContractTossedIn,
    DealerSelected,
    DealerSelectionStarted,
    DrawMade,
    DrawTied,
    GameConfigured,
    GameEvent,
    GameOver,
    MeldExposed,
    PlayBegun,
    RoundAbandoned,
    RoundScored,
    RoundStarted,
    SeatThinking,
    TrickCleared,
    TrickCompleted,
    TrumpNamed,
    TurnPrompt,
)
from pinochle.web.card_codec import encode_card, encode_suit
from pinochle.web.transport_events import GameAbandoned, SeatLost, SeatRejoined

AnyEvent = GameEvent | SeatLost | SeatRejoined | GameAbandoned


def encode_event(event: AnyEvent, seq: int, turn: dict) -> str:
    """Return one SSE frame for ``event``.

    Dispatches to the right payload builder and hands the result to
    ``encode_frame``, which owns the actual wire shape.
    """
    name, payload = _ENCODERS[type(event)](event)
    return encode_frame(name, seq, turn, payload)


def encode_frame(name: str, seq: int, turn: dict, payload: dict) -> str:
    """Return one SSE frame with the given name, sequence number, and payload.

    Frame shape per design.md §6.4: an ``id:`` line carrying the monotonic
    sequence number, an ``event:`` line naming the event in snake_case, and a
    ``data:`` line of compact JSON holding ``seq``, ``type``, the public
    ``turn`` header, and the event's own ``payload`` — terminated by a blank
    line.  ``json.dumps`` already escapes any newline embedded in a string
    field, so no frame can be split by its own payload.  Used directly for
    the one frame that isn't a ``GameEvent`` at all: ``stream_started``,
    built by the stream router itself when a connection opens (§6.2).

    Real sequence numbers start at 1, so ``seq=0`` marks that opening frame
    and its ``id:`` line is left off.  It has to be: the browser remembers
    the last ``id:`` it saw and sends it back as ``Last-Event-ID`` on the
    next reconnect (RT-5a), and an ``id: 0`` on every reconnect would wind
    that marker back to the start of the game each time.
    """
    data = json.dumps({"seq": seq, "type": name, "turn": turn, "payload": payload})
    head = "" if seq == 0 else f"id: {seq}\n"
    return f"{head}event: {name}\ndata: {data}\n\n"


def _game_configured(event: GameConfigured) -> tuple[str, dict]:
    """Build the payload for ``game_configured`` (UI-1, UI-3, UI-14)."""
    return "game_configured", {
        "seats": [
            {
                "player_id": p.id,
                "name": p.name,
                "type": p.type.name.lower(),
                "seat": p.position.name,
            }
            for p in event.players
        ],
        "teams": [{"team_id": t.id, "name": t.name} for t in event.teams],
        "winning_score": event.winning_score,
    }


def _dealer_selection_started(event: DealerSelectionStarted) -> tuple[str, dict]:
    """Build the payload for ``dealer_selection_started`` (FR-11a).

    ``taken`` is always empty: this event only fires when a spread is first
    laid out, before anyone has drawn from it.
    """
    return "dealer_selection_started", {"spread_size": event.spread_size, "taken": []}


def _draw_made(event: DrawMade) -> tuple[str, dict]:
    """Build the payload for ``draw_made`` (FR-11, FR-15)."""
    return "draw_made", {
        "player_id": event.player_id,
        "position": event.position,
        "card": encode_card(event.card),
    }


def _draw_tied(event: DrawTied) -> tuple[str, dict]:
    """Build the payload for ``draw_tied`` (FR-14)."""
    return "draw_tied", {
        "cards": {player_id: encode_card(card) for player_id, card in event.cards.items()},
    }


def _dealer_selected(event: DealerSelected) -> tuple[str, dict]:
    """Build the payload for ``dealer_selected`` (FR-13)."""
    return "dealer_selected", {"dealer_player_id": event.dealer_player_id}


def _round_started(event: RoundStarted) -> tuple[str, dict]:
    """Build the payload for ``round_started`` (FR-16)."""
    return "round_started", {
        "round_number": event.round_number,
        "dealer_player_id": event.dealer_player_id,
    }


def _cards_dealt(event: CardsDealt) -> tuple[str, dict]:
    """Build the payload for ``cards_dealt`` (FR-21, FR-22, NFR-6)."""
    return "cards_dealt", {"cards": [encode_card(c) for c in event.cards]}


def _bid_placed(event: BidPlaced) -> tuple[str, dict]:
    """Build the payload for ``bid_placed`` (FR-33)."""
    return "bid_placed", {
        "player_id": event.player_id,
        "amount": event.amount,
        "current_high": event.current_high,
    }


def _contract_offered(event: ContractOffered) -> tuple[str, dict]:
    """Build the payload for ``contract_offered`` (FR-32)."""
    return "contract_offered", {"player_id": event.player_id, "amount": event.amount}


def _round_abandoned(event: RoundAbandoned) -> tuple[str, dict]:
    """Build the payload for ``round_abandoned`` (FR-31, FR-32)."""
    return "round_abandoned", {"declined_by": event.declined_by}


def _trump_named(event: TrumpNamed) -> tuple[str, dict]:
    """Build the payload for ``trump_named`` (FR-36)."""
    return "trump_named", {"suit": encode_suit(event.suit)}


def _cards_passed(event: CardsPassed) -> tuple[str, dict]:
    """Build the payload for ``cards_passed`` (FR-38, FR-40)."""
    return "cards_passed", {
        "from_player_id": event.from_player_id,
        "to_player_id": event.to_player_id,
        "cards": [encode_card(c) for c in event.cards],
    }


def _meld_exposed(event: MeldExposed) -> tuple[str, dict]:
    """Build the payload for ``meld_exposed`` (FR-44, FR-45).

    ``MeldUnit`` does not record which specific cards make up a combination
    (only its name and point value), so a unit's cards aren't in this
    payload. Attributing exact cards would mean reworking
    ``pinochle.domain.meld.detect_meld`` to track them, which is deferred
    until the front end actually needs to highlight them.
    """
    return "meld_exposed", {
        "player_id": event.player_id,
        "units": [{"name": u.name, "points": u.points} for u in event.units],
        "total": event.total,
    }


def _play_begun(event: PlayBegun) -> tuple[str, dict]:
    """Build the payload for ``play_begun`` (FR-50a)."""
    return "play_begun", {"leader_player_id": event.leader_player_id}


def _contract_tossed_in(event: ContractTossedIn) -> tuple[str, dict]:
    """Build the payload for ``contract_tossed_in`` (FR-50b)."""
    return "contract_tossed_in", {"player_id": event.player_id}


def _seat_thinking(event: SeatThinking) -> tuple[str, dict]:
    """Build the payload for ``seat_thinking`` (RT-7, RT-10)."""
    return "seat_thinking", {"player_id": event.player_id}


def _card_played(event: CardPlayed) -> tuple[str, dict]:
    """Build the payload for ``card_played`` (FR-57)."""
    return "card_played", {"player_id": event.player_id, "card": encode_card(event.card)}


def _trick_completed(event: TrickCompleted) -> tuple[str, dict]:
    """Build the payload for ``trick_completed`` (FR-54, UI-15)."""
    return "trick_completed", {
        "winner_player_id": event.winner_player_id,
        "cards": [
            {"player_id": play.player_id, "card": encode_card(play.card)}
            for play in event.plays
        ],
    }


def _trick_cleared(event: TrickCleared) -> tuple[str, dict]:
    """Build the payload for ``trick_cleared`` (UI-15, RT-10)."""
    return "trick_cleared", {
        "winner_player_id": event.winner_player_id,
        "next_leader_player_id": event.next_leader_player_id,
    }


def _turn_prompt(event: TurnPrompt) -> tuple[str, dict]:
    """Build the payload for ``turn_prompt`` (UI-9, UI-10, §6.5).

    A tagged union on ``phase``; the fields beyond ``phase`` come straight
    from ``event.options``, except ``legal_plays`` while playing, whose
    cards need the wire codec.
    """
    options = dict(event.options)
    if "legal_plays" in options:
        options["legal_plays"] = [encode_card(c) for c in options["legal_plays"]]
    return "turn_prompt", {"phase": event.phase, **options}


def _round_scored(event: RoundScored) -> tuple[str, dict]:
    """Build the payload for ``round_scored`` (FR-66)."""
    return "round_scored", {
        "round_number": event.round_number,
        "bid_team_id": event.bid_team_id,
        "bid_winner_player_id": event.bid_winner_player_id,
        "contract": event.contract,
        "made_contract": event.made_contract,
        "tossed_in": event.tossed_in,
        "teams": [
            {
                "team_id": t.team_id,
                "meld": t.meld,
                "card_points": t.card_points,
                "last_trick_bonus": t.last_trick_bonus,
                "round_total": t.round_total,
                "points_applied": t.points_applied,
                "cumulative_score": t.cumulative_score,
            }
            for t in event.teams
        ],
    }


def _game_over(event: GameOver) -> tuple[str, dict]:
    """Build the payload for ``game_over`` (FR-71)."""
    return "game_over", {
        "winning_team_id": event.winning_team_id,
        "ns_score": event.ns_score,
        "ew_score": event.ew_score,
    }


def _seat_lost(event: SeatLost) -> tuple[str, dict]:
    """Build the payload for ``seat_lost`` (RT-12)."""
    return "seat_lost", {"player_id": event.player_id}


def _seat_rejoined(event: SeatRejoined) -> tuple[str, dict]:
    """Build the payload for ``seat_rejoined`` (RT-12)."""
    return "seat_rejoined", {"player_id": event.player_id}


def _game_abandoned(event: GameAbandoned) -> tuple[str, dict]:
    """Build the payload for ``game_abandoned`` (RT-12)."""
    return "game_abandoned", {"reason": event.reason}


_ENCODERS = {
    GameConfigured: _game_configured,
    DealerSelectionStarted: _dealer_selection_started,
    DrawMade: _draw_made,
    DrawTied: _draw_tied,
    DealerSelected: _dealer_selected,
    RoundStarted: _round_started,
    CardsDealt: _cards_dealt,
    BidPlaced: _bid_placed,
    ContractOffered: _contract_offered,
    RoundAbandoned: _round_abandoned,
    TrumpNamed: _trump_named,
    CardsPassed: _cards_passed,
    MeldExposed: _meld_exposed,
    PlayBegun: _play_begun,
    ContractTossedIn: _contract_tossed_in,
    SeatThinking: _seat_thinking,
    CardPlayed: _card_played,
    TrickCompleted: _trick_completed,
    TrickCleared: _trick_cleared,
    TurnPrompt: _turn_prompt,
    RoundScored: _round_scored,
    GameOver: _game_over,
    SeatLost: _seat_lost,
    SeatRejoined: _seat_rejoined,
    GameAbandoned: _game_abandoned,
}
