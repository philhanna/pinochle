# pinochle.web.turn_header
from pinochle.domain.game import Game, GamePhase


def build_turn_header(game: Game, thinking_player_id: str | None = None) -> dict:
    """Return the public ``turn`` object attached to every SSE frame (§6.4).

    Read from live game state rather than a snapshot captured when the
    paired event was dispatched. That is a deliberate simplification: the
    bounded, drop-on-full subscriber queues (§6.8) mean a connected reader
    is essentially never more than one event behind, so the two are
    indistinguishable in practice, and this avoids threading a captured
    header through ``NotificationPort``'s single-event signature.

    ``thinking_player_id``, once the computer driver exists (design.md §7),
    is the seat currently in its move delay, if any; it takes precedence
    over the trick-clear pause only because the two never overlap — a
    computer never has the lead into a table still holding a pending trick.
    """
    round_state = game.current_round
    if game.phase == GamePhase.IN_ROUND and round_state is not None:
        phase = round_state.phase.name
        current_player_id = round_state.current_player
        paused = "trick_clear" if round_state.trick_pending else None
    else:
        phase = game.phase.name
        current_player_id = None
        paused = None

    if paused is None and thinking_player_id is not None:
        paused = "thinking"

    return {
        "phase": phase,
        "current_player_id": current_player_id,
        "paused": paused,
        "round_number": game.round_number,
    }
