// Submitting this seat's actions.
//
// Every one is an ordinary HTTP request carrying the seat token in a header
// (FR-10a, ARC-7); nothing travels back this way. What the server did with an
// action arrives on the event stream like anybody else's move (RT-6), so these
// functions return only the failure, if there was one.

import { ApiError } from "./api.js";
import type { CardCode, SuitName } from "./cards.js";
import type { Seat } from "./types.js";

/** Draw a position from the face-down spread (FR-11, FR-11a). */
export async function draw(seat: Seat, position: number): Promise<void> {
  await send(seat, "draw", { position });
}

/** Bid an amount, or pass with `null` (FR-25, FR-26). */
export async function bid(seat: Seat, amount: number | null): Promise<void> {
  await send(seat, "bid", { amount });
}

/** Accept or decline a lone bidder's contract (FR-32). */
export async function decideContract(seat: Seat, accept: boolean): Promise<void> {
  await send(seat, "contract", { accept });
}

/** Name trump (FR-36). */
export async function nameTrump(seat: Seat, suit: SuitName): Promise<void> {
  await send(seat, "trump", { suit });
}

/** Pass exactly four cards to the partner (FR-38, FR-42). */
export async function passCards(seat: Seat, cards: CardCode[]): Promise<void> {
  await send(seat, "pass", { cards });
}

/** End the meld display and lead the first trick (FR-50a). */
export async function beginPlay(seat: Seat): Promise<void> {
  await send(seat, "begin-play");
}

/** Concede the contract without playing it out (FR-50b). */
export async function tossIn(seat: Seat): Promise<void> {
  await send(seat, "toss-in");
}

/**
 * Release the hold the table is stopped on, from this seat (RT-13, UI-19a).
 *
 * `holdId` names which hold, so a click that arrived a moment late releases
 * nothing rather than releasing whatever hold came next. The server treats a
 * hold that has already ended as success, so nothing here has to guard
 * against another seat having got there first.
 */
export async function acknowledge(seat: Seat, holdId: number): Promise<void> {
  await send(seat, "acknowledge", { hold_id: holdId });
}

/** Play one card (FR-57). */
export async function play(seat: Seat, card: CardCode): Promise<void> {
  await send(seat, "play", { card });
}

/**
 * POST one action, raising `ApiError` with the server's own words if refused.
 *
 * A refusal is expected traffic rather than an exception: NFR-4 has the server
 * reject an action submitted at the wrong time or by the wrong seat and leave
 * the game exactly as it was, so the client's job is to say what it said.
 */
async function send(seat: Seat, action: string, body?: unknown): Promise<void> {
  const response = await fetch(
    `/api/games/${encodeURIComponent(seat.gameId)}/${action}`,
    {
      method: "POST",
      headers: {
        "X-Seat-Token": seat.token,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    },
  );

  if (response.ok) {
    return;
  }

  const text = await response.text();
  let code = String(response.status);
  let message = `The server refused that (${response.status}).`;
  try {
    const error = (JSON.parse(text) as { error?: { code?: string; message?: string } }).error;
    code = error?.code ?? code;
    message = error?.message ?? message;
  } catch {
    // A non-JSON body means something other than the application answered.
  }
  throw new ApiError(code, message);
}
