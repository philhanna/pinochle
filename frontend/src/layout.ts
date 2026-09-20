// Where things sit on the table, and what may be done to them.
//
// Pure derivations from the state, kept apart from the DOM so they can be
// tested headlessly — which matters here because the rest of the table is
// exactly the part a test cannot look at.

import type { CardCode, SuitName } from "./cards.js";
import type { GameState, Play, SeatInfo } from "./state.js";

/** Where a seat is drawn, from the viewing player's point of view. */
export type Spot = "bottom" | "left" | "top" | "right";

/** The four seats, placed around the table as this client sees them. */
export type Placement = Record<Spot, SeatInfo | null>;

// FR-3's clockwise turn order. The seat that plays after you sits to your
// left, which is what UI-1's "true clockwise relationship" comes to on screen.
const CLOCKWISE = ["NORTH", "EAST", "SOUTH", "WEST"] as const;

/**
 * Place the four seats with this client's own seat at the bottom (UI-1).
 *
 * The next seat in turn order goes to the left, the partner across, and the
 * seat that plays before you to the right. Before the table is known — or for
 * a client with no seat at all — every spot is empty.
 */
export function placement(state: GameState): Placement {
  const me = state.me;
  if (me === null || state.seats.length === 0) {
    return { bottom: null, left: null, top: null, right: null };
  }
  const base = CLOCKWISE.indexOf(me.seat);
  const at = (offset: number): SeatInfo | null => {
    const name = CLOCKWISE[(base + offset) % CLOCKWISE.length];
    return state.seats.find((seat) => seat.seat === name) ?? null;
  };
  return { bottom: at(0), left: at(1), top: at(2), right: at(3) };
}

/** The spot a seat occupies, or null if it is not at this table. */
export function spotOf(state: GameState, playerId: string): Spot | null {
  const spots = placement(state);
  for (const spot of ["bottom", "left", "top", "right"] as const) {
    if (spots[spot]?.playerId === playerId) {
      return spot;
    }
  }
  return null;
}

/** One card in the trick, tagged with the spot it was played from (UI-6). */
export interface TrickCard extends Play {
  spot: Spot;
}

/**
 * The trick, each card tagged with where to draw it (UI-6).
 *
 * Every card is placed nearer the seat that played it, so all four stay
 * visible and attributable rather than piling up in the middle.
 */
export function trickCards(state: GameState, plays: Play[] = state.trick): TrickCard[] {
  return plays.flatMap((play) => {
    const spot = spotOf(state, play.playerId);
    return spot === null ? [] : [{ ...play, spot }];
  });
}

/**
 * Whether `card` may be played right now (UI-9).
 *
 * The answer is the server's: legality comes from the turn prompt, never from
 * rules re-implemented here (ARC-2). No prompt means it is not this seat's
 * turn, so nothing is playable.
 *
 * Nothing is playable during a pause either. A timed pause is a state the game
 * occupies, not a presentation effect, and an action that would advance past
 * one is rejected exactly as any other out-of-phase action (RT-9) — "The
 * completed trick has not been cleared yet." So the next leader is not offered
 * a card it would only be refused for.
 */
export function isLegalPlay(state: GameState, card: CardCode): boolean {
  if (isPaused(state)) {
    return false;
  }
  const legal = state.prompt?.phase === "PLAYING" ? state.prompt.legalPlays : undefined;
  return legal !== undefined && legal.includes(card);
}

/** Whether this seat is being asked to act at all. */
export function isMyTurn(state: GameState): boolean {
  return state.me !== null && state.currentPlayerId === state.me.playerId;
}

/** Whether the table is waiting on a pause the server owns (RT-9). */
export function isPaused(state: GameState): boolean {
  return state.paused !== null;
}

/**
 * Whether this seat still has to draw for the deal (FR-11).
 *
 * Dealer selection has no turn, so the prompt says nothing: a seat has a draw
 * to make while the phase is dealer selection and none of the drawn cards is
 * its own.
 */
export function mustDraw(state: GameState): boolean {
  return (
    state.me !== null
    && state.phase === "DEALER_SELECTION"
    && !state.draws.some((draw) => draw.playerId === state.me?.playerId)
  );
}

/** The positions already taken out of the spread (FR-11a). */
export function takenPositions(state: GameState): Set<number> {
  return new Set(state.draws.map((draw) => draw.position));
}

/** The four suits, in the order the trump picker offers them (UI-11). */
export const SUITS: SuitName[] = ["SPADES", "HEARTS", "DIAMONDS", "CLUBS"];

/** The symbol and colour a suit is drawn with. */
export function suitGlyph(suit: SuitName): { glyph: string; red: boolean } {
  switch (suit) {
    case "SPADES": return { glyph: "♠", red: false };
    case "HEARTS": return { glyph: "♥", red: true };
    case "DIAMONDS": return { glyph: "♦", red: true };
    case "CLUBS": return { glyph: "♣", red: false };
  }
}

/** How many cards this seat must still choose for the pass (FR-42). */
export function passCount(state: GameState): number {
  return state.prompt?.phase === "PASSING" ? state.prompt.count ?? 4 : 0;
}

/** The lowest bid this seat may make, or null if it is not bidding (UI-10). */
export function minimumBid(state: GameState): number | null {
  return state.prompt?.phase === "BIDDING" ? state.prompt.minimumBid ?? null : null;
}
