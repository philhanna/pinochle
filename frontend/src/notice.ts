// What the table has just been told (UI-19).
//
// One sentence, naming the outcome of the stage of play that has just
// concluded: who won the draw, who won the auction, what trump is, who took
// the trick, how the round scored. It is derived here rather than sent as
// text, because every fact it states already crossed the wire as an event and
// the event is the authoritative copy — a second copy in prose could disagree
// with the first.
//
// Pure, like view.ts and layout.ts: this is the text a reviewer would
// otherwise have to read off a screenshot.

import { suitGlyph } from "./layout.js";
import { gameOverText, nameOf, summaryHeadline } from "./view.js";
import type { GameState, Hold } from "./state.js";

/** The one message the notice area is showing. */
export interface Notice {
  text: string;
  /** `hold` while the game is stopped, `final` once it is over (UI-19a). */
  kind: "result" | "hold" | "final";
  /**
   * Identifies the message, so a redraw on an unrelated frame is not a change.
   *
   * Every frame carries the turn header and so rebuilds this, but most frames
   * rebuild it identically. A renderer that animates, or that scrolls, wants
   * to act when the notice becomes a different one — not thirty times while it
   * stays the same.
   */
  key: string;
  /**
   * The hold a control here should release, or null if there is nothing to
   * click (UI-19a).
   *
   * Any seated player may use it (RT-13), so this is the same for all four
   * clients; none of them needs to ask whether the button is theirs.
   */
  release: number | null;
}

/** The notice this state calls for, or null when the table has nothing to say. */
export function notice(state: GameState): Notice | null {
  if (state.gameOver !== null) {
    return { text: gameOverText(state), kind: "final", key: "game-over", release: null };
  }
  return state.hold === null ? standing(state) : held(state, state.hold);
}

/**
 * What to say while the game is stopped (RT-13).
 *
 * A reason the client does not recognise still produces a notice rather than
 * nothing: an unnamed pause is better than a table that has silently stopped,
 * and if the hold is one a player must release, UI-19a needs somewhere to put
 * the control regardless of whether this client knows what it is waiting for.
 */
function held(state: GameState, hold: Hold): Notice {
  const release = hold.ackable ? hold.id : null;
  const say = (text: string, mark: string | number | null): Notice => ({
    text,
    kind: "hold",
    key: keyFor(hold, mark),
    release,
  });

  switch (hold.reason) {
    case "trick_clear":
      return say(
        state.trickWinnerPlayerId === null
          ? "Gathering the trick…"
          : `${nameOf(state, state.trickWinnerPlayerId)} takes the trick.`,
        tricksPlayed(state),
      );
    case "thinking":
      return say(
        state.thinkingPlayerId === null
          ? "Thinking…"
          : `${nameOf(state, state.thinkingPlayerId)} is thinking…`,
        state.thinkingPlayerId,
      );
    case "draw_tied":
      return say("Tied for high card — the deck is thrown again.", state.spreadId);
    case "dealer_selected":
      return say(dealerText(state), state.dealerPlayerId);
    case "round_abandoned":
      return say("Nobody took the contract — the deal moves on.", state.roundNumber);
    case "round_scored": {
      // The hold is on the turn header of the frame that gathers the last
      // trick, which arrives before ``round_scored`` itself: for that one
      // frame there is no summary to headline. A band holding nothing but a
      // Continue button is worse than a sentence replaced a moment later.
      const headline = summaryHeadline(state);
      return say(
        headline === "" ? "The round is over." : headline,
        state.roundSummary?.roundNumber ?? null,
      );
    }
    default:
      return say("The game is paused.", hold.reason);
  }
}

/**
 * What to say while play is running: the most recent thing to have concluded.
 *
 * Ordered newest first, so each stage's result replaces the one before it and
 * stays up until the next stage concludes (UI-19). The contract and trump are
 * on the scoreboard for the whole round anyway (UI-14), so once a trick has
 * been taken the notice moves on to that rather than repeating them.
 * During the auction, each bid or pass replaces the previous action so every
 * player at the table can follow it without opening the scoreboard.
 *
 * The announcements from before the cards were led have a shorter life than
 * that: they end when the first card of the round is played, whether or not
 * anything has replaced them. Who deals and what the contract is are settled
 * facts by then, both of them already on the table -- the dealer on the seat's
 * own label, the contract and trump on the scoreboard for the whole round
 * (UI-14) -- so a band still announcing them is saying something the table has
 * moved past. The notice says nothing at all until the first trick is taken,
 * which is the next thing to actually conclude.
 */
function standing(state: GameState): Notice | null {
  const say = (text: string, key: string): Notice =>
    ({ text, kind: "result", key, release: null });

  if (state.roundSummary !== null) {
    return say(summaryHeadline(state), `summary:${state.roundSummary.roundNumber}`);
  }
  if (state.tossedInBy !== null) {
    return say(
      `${nameOf(state, state.tossedInBy)} tossed the contract in.`,
      `toss:${state.tossedInBy}`,
    );
  }
  if (state.lastTrick !== null) {
    const who = nameOf(state, state.lastTrick.winnerPlayerId);
    return say(`${who} took the last trick.`, `took:${tricksPlayed(state)}`);
  }
  if (state.trick.length > 0) {
    return null;
  }
  if (state.contract !== null) {
    return say(contractText(state), `contract:${state.contract.amount}:${state.trump ?? ""}`);
  }
  if (state.offer !== null) {
    const who = nameOf(state, state.offer.playerId);
    return say(
      `${who} bid ${state.offer.amount} alone, and is deciding whether to take it.`,
      `offer:${state.offer.playerId}:${state.offer.amount}`,
    );
  }
  const latestBid = state.bids.at(-1);
  if (latestBid !== undefined) {
    const who = nameOf(state, latestBid.playerId);
    const action = latestBid.amount === null
      ? `${who} passes.`
      : `${who} bids ${latestBid.amount}.`;
    return say(action, `bid:${state.bids.length}`);
  }
  if (state.dealerPlayerId !== null) {
    return say(dealerText(state), `dealer:${state.dealerPlayerId}`);
  }
  return null;
}

/** The auction's outcome, with trump once it has been named (FR-30, FR-36). */
function contractText(state: GameState): string {
  const contract = state.contract;
  if (contract === null) {
    return "";
  }
  const who = nameOf(state, contract.playerId);
  if (state.trump === null) {
    return `${who} won the auction at ${contract.amount}.`;
  }
  const { glyph } = suitGlyph(state.trump);
  return `${who} plays ${contract.amount} in ${glyph} ${state.trump.toLowerCase()}.`;
}

/** Who deals, once the draw has settled it (FR-13). */
function dealerText(state: GameState): string {
  return state.dealerPlayerId === null
    ? "Drawing for the deal."
    : `${nameOf(state, state.dealerPlayerId)} deals.`;
}

/**
 * How many tricks have been gathered this round, both teams together.
 *
 * Used only to tell one trick from the next in a notice's key. It is a count
 * of tricks, never of the points in them, which UI-14c keeps off the screen
 * until the round is over.
 */
function tricksPlayed(state: GameState): number {
  return Object.values(state.tricksTaken).reduce((total, taken) => total + taken, 0);
}

/**
 * A key that changes when the hold does.
 *
 * A named hold has an id and needs nothing else. One derived from the older
 * `paused` field has no id, so it is distinguished by what it is about —
 * which trick, which seat, which spread — and two consecutive holds of the
 * same reason are told apart by that.
 */
function keyFor(hold: Hold, mark: string | number | null): string {
  return hold.id === null ? `${hold.reason}:${mark ?? ""}` : `hold:${hold.id}`;
}
