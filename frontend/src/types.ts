// The wire contract, as the server's event encoder defines it.
//
// Every frame the server sends carries the same four fields, and every frame
// carries the public turn header — the client is never left inferring whose
// turn it is or whether the table is paused (RT-8, RT-10).

/**
 * A server-owned pause, named so the client can say what it is for (RT-13).
 *
 * `ackable` is the whole difference a player can see: a timed hold runs out
 * by itself, while one awaiting release shows a control and waits for any one
 * seat to use it (UI-19a). `id` is what that release names, so that a second
 * click — or a second player's click — lands on a hold that has already ended
 * and changes nothing.
 */
export interface HoldHeader {
  id: number;
  reason: string;
  ackable: boolean;
}

/** The public turn header attached to every frame. */
export interface TurnHeader {
  phase: string;
  current_player_id: string | null;
  /** A server-owned pause the client renders but does not time (RT-8). */
  paused: "trick_clear" | "thinking" | null;
  /** The same pause, named (RT-13). Absent until the server sends holds. */
  hold?: HoldHeader | null;
  round_number: number;
}

/** One decoded SSE frame. */
export interface Frame {
  seq: number;
  type: FrameType;
  turn: TurnHeader;
  payload: Record<string, unknown>;
}

/**
 * Every frame name the server can send.
 *
 * `EventSource` has no wildcard listener and the server names every frame on
 * its `event:` line, so a client must subscribe to each name explicitly.
 * That makes this list load-bearing: a name missing here is a frame silently
 * never received.
 */
export const FRAME_TYPES = [
  // Opened by the stream router itself, not by the domain (§6.2).
  "stream_started",
  // Setup and dealer selection.
  "game_configured",
  // An amendment to the table: a computer has taken a seat over from a
  // player who left (RT-12a).
  "seat_replaced",
  "dealer_selection_started",
  "draw_made",
  "draw_tied",
  "dealer_selected",
  // Deal.
  "round_started",
  "cards_dealt",
  // Bidding.
  "bid_placed",
  "contract_offered",
  "round_abandoned",
  // Trump and the pass.
  "trump_named",
  "cards_passed",
  // Meld.
  "meld_exposed",
  // Play.
  "play_begun",
  "contract_tossed_in",
  "seat_thinking",
  "card_played",
  "trick_completed",
  "trick_cleared",
  "turn_prompt",
  // End of round and game.
  "round_scored",
  "game_over",
  // The start and end of a pause (RT-10). What they say is also on the turn
  // header of every frame, which is what a client that missed them reads.
  "hold_begun",
  "hold_ended",
  // Published by the transport rather than the domain.  Not acted on in this
  // release: the client logs them and renders nothing (docs/impl.md §6).
  "seat_lost",
  "seat_rejoined",
  "game_abandoned",
] as const;

export type FrameType = (typeof FRAME_TYPES)[number];

/** The seat this tab is playing, as resolved from the join link. */
export interface Seat {
  gameId: string;
  token: string;
}
