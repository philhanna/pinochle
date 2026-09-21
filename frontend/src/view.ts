// What the table says in words: the scoreboard, the bid history, the meld
// totals, the round summary, the status line.
//
// Pure, for the same reason as layout.ts: this is the text a reviewer would
// otherwise have to read off a screenshot.

import { suitGlyph } from "./layout.js";
import type { GameState, SeatInfo } from "./state.js";

/** One line of the persistent scoreboard (UI-14, UI-14a). */
export interface ScoreLine {
  label: string;
  value: string;
}

/**
 * The scoreboard: scores, contract, auction winner, trump, and the meld
 * totals that stay up for the whole round (UI-14, UI-14a).
 *
 * Deliberately no running card-point total (UI-14c): counting the cards as
 * they fall is part of playing well.
 */
export function scoreboard(state: GameState): ScoreLine[] {
  const lines: ScoreLine[] = state.teams.map((team) => ({
    label: team.name,
    value: `${team.score}${meldSuffix(state, team.teamId)}`,
  }));

  lines.push({ label: "Round", value: state.roundNumber === 0 ? "—" : String(state.roundNumber) });
  lines.push({ label: "Contract", value: contractText(state) });
  lines.push({ label: "Trump", value: trumpText(state) });
  if (state.winningScore > 0) {
    lines.push({ label: "Playing to", value: String(state.winningScore) });
  }
  return lines;
}

/** A team's meld for this round, shown beside its score once there is any. */
function meldSuffix(state: GameState, teamId: string): string {
  const meld = state.teamMeld[teamId];
  return meld === undefined || meld === 0 ? "" : `  (+${meld} meld)`;
}

/** The contract and who holds it, in words (UI-14). */
export function contractText(state: GameState): string {
  const contract = state.contract;
  if (contract === null) {
    return state.offer === null ? "—" : `${state.offer.amount} offered`;
  }
  return `${contract.amount} — ${nameOf(state, contract.playerId)}`;
}

/** The trump suit, with its symbol (UI-14). */
export function trumpText(state: GameState): string {
  if (state.trump === null) {
    return "—";
  }
  const { glyph } = suitGlyph(state.trump);
  return `${glyph} ${titleCase(state.trump)}`;
}

/** The bid history, kept for the whole round (UI-10, UI-14a). */
export function bidHistory(state: GameState): string[] {
  return state.bids.map((bid) => {
    const who = nameOf(state, bid.playerId);
    return bid.amount === null ? `${who}: pass` : `${who}: ${bid.amount}`;
  });
}

/** The latest auction call to show beside one player's hand. */
export function bidCall(state: GameState, playerId: string): string | null {
  if (state.contract !== null) {
    return null;
  }
  for (let index = state.bids.length - 1; index >= 0; index -= 1) {
    const bid = state.bids[index];
    if (bid?.playerId === playerId) {
      return bid.amount === null ? "pass" : String(bid.amount);
    }
  }
  return null;
}

/** One seat's exposed meld, for the table's meld display (UI-13). */
export interface MeldLine {
  playerId: string;
  name: string;
  units: string[];
  total: number;
}

/** Each seat's meld, in seat order (UI-13). */
export function meldLines(state: GameState): MeldLine[] {
  return state.seats
    .filter((seat) => state.meld[seat.playerId] !== undefined)
    .map((seat) => {
      const meld = state.meld[seat.playerId];
      return {
        playerId: seat.playerId,
        name: seat.name,
        units: (meld?.units ?? []).map((unit) => `${unit.name} ${unit.points}`),
        total: meld?.total ?? 0,
      };
    });
}

/**
 * Whether the exposed meld is still lying on the table (UI-13, UI-14a).
 *
 * Which combinations a seat showed is public while the cards are face-up in
 * front of it; once they are gathered up, UI-14a keeps the totals and lets the
 * detail go. The first trick gathered to its winner is when that happens —
 * meld is exposed before play, and the table is cleared for the first time
 * when that trick is taken in.
 */
export function meldIsExposed(state: GameState): boolean {
  return state.lastTrick === null;
}

/** One row of the round summary (FR-66). */
export interface SummaryRow {
  teamId: string;
  name: string;
  meld: number;
  cardPoints: number;
  lastTrickBonus: number;
  roundTotal: number;
  pointsApplied: number;
  cumulativeScore: number;
  bid: boolean;
}

/** The round summary, the one place card points appear (FR-66, UI-14c). */
export function summaryRows(state: GameState): SummaryRow[] {
  const summary = state.roundSummary;
  if (summary === null) {
    return [];
  }
  return summary.teams.map((team) => ({
    teamId: team.teamId,
    name: state.teams.find((t) => t.teamId === team.teamId)?.name ?? team.teamId,
    meld: team.meld,
    cardPoints: team.cardPoints,
    lastTrickBonus: team.lastTrickBonus,
    roundTotal: team.roundTotal,
    pointsApplied: team.pointsApplied,
    cumulativeScore: team.cumulativeScore,
    bid: team.teamId === summary.bidTeamId,
  }));
}

/** The headline over the round summary (FR-66). */
export function summaryHeadline(state: GameState): string {
  const summary = state.roundSummary;
  if (summary === null) {
    return "";
  }
  const winner = nameOf(state, summary.bidWinnerPlayerId);
  if (summary.tossedIn) {
    return `Round ${summary.roundNumber}: ${winner} tossed in the ${summary.contract} contract.`;
  }
  const outcome = summary.madeContract ? "made" : "went set on";
  return `Round ${summary.roundNumber}: ${winner} ${outcome} the ${summary.contract} contract.`;
}

/** The game's result, once there is one (FR-71). */
export function gameOverText(state: GameState): string {
  const over = state.gameOver;
  if (over === null) {
    return "";
  }
  const name = state.teams.find((t) => t.teamId === over.winningTeamId)?.name ?? over.winningTeamId;
  return `${name} team wins, ${over.nsScore} to ${over.ewScore}.`;
}

/**
 * The one-line status: whose turn it is, and what they are being asked for.
 *
 * A pause used to be reported here as well. It is the notice area's now
 * (UI-19): a pause is a state the game occupies (RT-9), and what the table is
 * being held for is exactly what a notice says. Saying it in both places left
 * the two lines paraphrasing each other.
 */
export function statusLine(state: GameState): string {
  if (state.gameOver !== null) {
    return gameOverText(state);
  }
  if (state.phase === "DEALER_SELECTION") {
    return "Drawing for the deal — pick a card.";
  }
  if (state.phase === "DEALING") {
    return "Dealing the cards…";
  }
  if (state.phase === "SETUP") {
    return "Waiting for the game to start…";
  }
  if (state.currentPlayerId === null) {
    return "";
  }
  const mine = state.currentPlayerId === state.me?.playerId;
  const who = mine ? "Your" : `${nameOf(state, state.currentPlayerId)}'s`;
  return `${who} turn — ${phraseFor(state.phase)}`;
}

/** What a round phase is called on screen. */
function phraseFor(phase: string): string {
  switch (phase) {
    case "BIDDING": return "bidding";
    case "CONFIRMING": return "accept or decline the contract";
    case "TRUMP": return "name trump";
    case "PASSING": return "pass four cards";
    case "MELDING": return "meld";
    case "PLAYING": return "play a card";
    default: return phase.toLowerCase();
  }
}

/** A seat's display name, or its id if the table is not known yet. */
export function nameOf(state: GameState, playerId: string): string {
  return state.seats.find((seat) => seat.playerId === playerId)?.name ?? playerId;
}

/** A seat's label: name, and "dealer" where it applies (UI-3). */
export function seatLabel(state: GameState, seat: SeatInfo): string {
  return seat.playerId === state.dealerPlayerId ? `${seat.name} (dealer)` : seat.name;
}

/** Turn "SPADES" into "Spades". */
function titleCase(word: string): string {
  return word.slice(0, 1) + word.slice(1).toLowerCase();
}
