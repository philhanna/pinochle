// The visible deal.
//
// The server sends this seat its complete private hand in one event. This
// module turns that completed fact into the way it happened at the table:
// three cards at a time, beginning left of the dealer and moving clockwise.

import type { GameState } from "./state.js";

/** A deliberate but comfortable human rhythm for placing one packet. */
export const DEAL_PACKET_MS = 400;

const CLOCKWISE = ["NORTH", "EAST", "SOUTH", "WEST"] as const;
const CARDS_PER_PACKET = 3;
const PACKETS_PER_SEAT = 4;

/** The total number of packets in one four-player pinochle deal. */
export const DEAL_PACKET_COUNT = CLOCKWISE.length * PACKETS_PER_SEAT;

/** Player ids in deal order, beginning with the seat left of the dealer. */
export function dealOrder(state: GameState): string[] {
  const dealer = state.seats.find((seat) => seat.playerId === state.dealerPlayerId);
  if (dealer === undefined) {
    return state.seats.map((seat) => seat.playerId);
  }
  const dealerIndex = CLOCKWISE.indexOf(dealer.seat);
  return Array.from({ length: CLOCKWISE.length }, (_, offset) => {
    const seatName = CLOCKWISE[(dealerIndex + 1 + offset) % CLOCKWISE.length];
    return state.seats.find((seat) => seat.seat === seatName)?.playerId;
  }).filter((playerId): playerId is string => playerId !== undefined);
}

/**
 * Project a completed hand as it looks after `packetCount` packets.
 *
 * The authoritative state is untouched. Hiding its prompt also makes the
 * visible deal non-interactive; queued stream frames are applied after the
 * six-second presentation completes.
 */
export function dealingView(state: GameState, packetCount: number): GameState {
  const order = dealOrder(state);
  const counts = Object.fromEntries(state.seats.map((seat) => [seat.playerId, 0]));
  const shown = Math.max(0, Math.min(DEAL_PACKET_COUNT, packetCount));
  for (let packet = 0; packet < shown; packet += 1) {
    const playerId = order[packet % order.length];
    if (playerId !== undefined) {
      counts[playerId] = (counts[playerId] ?? 0) + CARDS_PER_PACKET;
    }
  }

  const mine = state.me === null ? 0 : counts[state.me.playerId] ?? 0;
  return {
    ...state,
    hand: state.hand.slice(0, mine),
    handCounts: counts,
    phase: "DEALING",
    currentPlayerId: null,
    thinkingPlayerId: null,
    prompt: null,
  };
}
