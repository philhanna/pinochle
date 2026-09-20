// The client's model of the game.
//
// RT-5 puts no snapshot on the server: a client builds its whole view from the
// frames it has received since it joined, and a client that loses its stream
// cannot rebuild one. So this reducer is not a cache of something
// authoritative elsewhere — it is the only model the browser has, and every
// later rendering slice draws from it alone.
//
// Two rules follow, and both are enforced by tests:
//
//   * It holds no card-point total for a round in progress (UI-14c). Counting
//     the cards as they fall is part of playing well; trick points appear only
//     in the round summary, after play is over.
//   * It holds only this seat's own cards. Other hands are counts (UI-5), and
//     the server never sends anything else (NFR-6).

import { removeOne, sortHand, type CardCode, type SuitName } from "./cards.js";
import type { Frame, FrameType, TurnHeader } from "./types.js";

/** A seat name as the wire gives it. */
export type SeatName = "NORTH" | "EAST" | "SOUTH" | "WEST";

/** Which partnership a seat belongs to. */
export type TeamId = "NS" | "EW";

/** Who is playing a seat. */
export interface SeatInfo {
  playerId: string;
  name: string;
  type: "human" | "computer";
  seat: SeatName;
  teamId: TeamId;
}

/** A partnership and its running score. */
export interface TeamInfo {
  teamId: string;
  name: string;
  score: number;
}

/** One card played by one seat. */
export interface Play {
  playerId: string;
  card: CardCode;
}

/** One scoring combination a seat exposed. */
export interface MeldUnit {
  name: string;
  points: number;
}

/** A seat's exposed meld (FR-44, UI-13). */
export interface PlayerMeld {
  units: MeldUnit[];
  total: number;
}

/** A completed trick, kept for review during the next one (UI-14b). */
export interface CompletedTrick {
  plays: Play[];
  winnerPlayerId: string;
}

/** One bid or pass, in the order it was made (UI-10, UI-14a). */
export interface BidRecord {
  playerId: string;
  amount: number | null;
}

/** A card drawn from the dealer-selection spread (FR-11a). */
export interface Draw {
  playerId: string;
  position: number;
  card: CardCode;
}

/**
 * What this seat has been asked to do (§6.5).
 *
 * A tagged union on `phase`, sent privately to the seat whose turn it is.
 * `legalPlays` is the one the table needs most: UI-9 requires legal cards be
 * distinguishable, and ARC-2 means the client may not work out legality for
 * itself.
 */
export interface Prompt {
  phase: string;
  minimumBid?: number;
  mayPass?: boolean;
  amount?: number;
  count?: number;
  mayBeginPlay?: boolean;
  mayTossIn?: boolean;
  legalPlays?: CardCode[];
}

/** One team's arithmetic for a finished round (FR-66). */
export interface TeamRoundScore {
  teamId: string;
  meld: number;
  cardPoints: number;
  lastTrickBonus: number;
  roundTotal: number;
  pointsApplied: number;
  cumulativeScore: number;
}

/** The summary shown once play is over (FR-66). */
export interface RoundSummary {
  roundNumber: number;
  bidTeamId: string;
  bidWinnerPlayerId: string;
  contract: number;
  madeContract: boolean;
  tossedIn: boolean;
  teams: TeamRoundScore[];
}

/** The whole client-side model. */
export interface GameState {
  /** This seat, from `stream_started`; null until the stream opens. */
  me: SeatInfo | null;
  /** Whether the stream opened into a round already in progress (RT-5). */
  partial: boolean;
  seats: SeatInfo[];
  teams: TeamInfo[];
  winningScore: number;

  spreadSize: number;
  draws: Draw[];
  dealerPlayerId: string | null;

  roundNumber: number;
  /** This seat's own cards, in display order (FR-23, FR-23a). */
  hand: CardCode[];
  /** How many cards each seat holds, this one included (UI-5). */
  handCounts: Record<string, number>;

  bids: BidRecord[];
  highBid: number;
  /** A lone bidder's offer, while they decide whether to be held to it (FR-32). */
  offer: { playerId: string; amount: number } | null;
  contract: { playerId: string; amount: number } | null;
  trump: SuitName | null;

  /** The pass this seat received, if any — team-private (FR-40, RT-1). */
  received: { fromPlayerId: string; cards: CardCode[] } | null;
  /** The pass this seat sent, if any. */
  sent: { toPlayerId: string; cards: CardCode[] } | null;

  meld: Record<string, PlayerMeld>;
  /** Each team's meld total, kept for the whole round (UI-14a). */
  teamMeld: Record<string, number>;

  leaderPlayerId: string | null;
  trick: Play[];
  /** Set while a completed trick is still on the table (UI-15). */
  trickWinnerPlayerId: string | null;
  lastTrick: CompletedTrick | null;
  /** Tricks taken per team. A count, never a card-point total (UI-14c). */
  tricksTaken: Record<string, number>;
  tossedInBy: string | null;

  /** The seat currently inside its move delay (RT-7, RT-10). */
  thinkingPlayerId: string | null;
  prompt: Prompt | null;

  phase: string;
  currentPlayerId: string | null;
  paused: TurnHeader["paused"];

  roundSummary: RoundSummary | null;
  gameOver: { winningTeamId: string; nsScore: number; ewScore: number } | null;

  /**
   * The highest sequence number seen.
   *
   * Monotonic but not contiguous: frames addressed to other seats consume
   * numbers, so this seat sees gaps and must never wait for a missing one.
   */
  lastSeq: number;
}

/** The state of a client that has not yet received a frame. */
export function initialState(): GameState {
  return {
    me: null,
    partial: false,
    seats: [],
    teams: [],
    winningScore: 0,
    spreadSize: 0,
    draws: [],
    dealerPlayerId: null,
    roundNumber: 0,
    hand: [],
    handCounts: {},
    bids: [],
    highBid: 0,
    offer: null,
    contract: null,
    trump: null,
    received: null,
    sent: null,
    meld: {},
    teamMeld: {},
    leaderPlayerId: null,
    trick: [],
    trickWinnerPlayerId: null,
    lastTrick: null,
    tricksTaken: {},
    tossedInBy: null,
    thinkingPlayerId: null,
    prompt: null,
    phase: "SETUP",
    currentPlayerId: null,
    paused: null,
    roundSummary: null,
    gameOver: null,
    lastSeq: -1,
  };
}

/**
 * Fold one frame into the state, returning a new state.
 *
 * Never mutates its argument, so a renderer may keep the previous state and
 * compare. Every frame carries the turn header, so phase, turn and pause are
 * refreshed from every frame regardless of its type — the client is never left
 * inferring them (RT-8, RT-10).
 */
export function applyEvent(state: GameState, frame: Frame): GameState {
  const next = { ...applyPayload(state, frame), ...fromHeader(frame.turn) };
  next.lastSeq = Math.max(state.lastSeq, frame.seq);
  return withLivePrompt(next);
}

/**
 * Drop a prompt the table has already moved past (§6.5, NFR-4).
 *
 * The server builds a prompt from the round's phase and the seat on the
 * clock, and sends it to that seat alone; the turn header on every frame
 * carries those same two facts. So a prompt is good only while the header
 * still agrees with it, and one that disagrees has been overtaken — by the
 * melding ending, by the turn passing, by a phase the server has already left.
 *
 * Without this the client goes on offering the controls for whatever it was
 * last asked, and the only thing that stops a player using them is the server
 * refusing the action (NFR-4), which is not where a client should leave it.
 */
function withLivePrompt(state: GameState): GameState {
  const prompt = state.prompt;
  if (prompt === null) {
    return state;
  }
  const mine = state.me !== null && state.currentPlayerId === state.me.playerId;
  return mine && prompt.phase === state.phase ? state : { ...state, prompt: null };
}

/** Apply the parts of a frame that depend on its type. */
function applyPayload(state: GameState, frame: Frame): GameState {
  const handler = HANDLERS[frame.type];
  return handler === undefined ? state : handler(state, frame.payload);
}

/** Read phase, turn and pause from the header every frame carries. */
function fromHeader(turn: TurnHeader): Pick<GameState, "phase" | "currentPlayerId" | "paused"> {
  return {
    phase: turn.phase,
    currentPlayerId: turn.current_player_id,
    paused: turn.paused,
  };
}

/** One frame type's contribution to the state. */
type Handler = (state: GameState, payload: Record<string, unknown>) => GameState;

/**
 * The partnership a seat belongs to (FR-4a).
 *
 * Derived from the seat, never carried alongside it: it is impossible to
 * represent a player seated North who belongs to East/West.
 */
export function teamOf(seat: SeatName): TeamId {
  return seat === "NORTH" || seat === "SOUTH" ? "NS" : "EW";
}

/** The seat occupying `playerId`, if the table is known yet. */
export function seatOf(state: GameState, playerId: string): SeatInfo | null {
  return state.seats.find((s) => s.playerId === playerId) ?? null;
}

/** Whether `playerId` is this seat's partner. */
export function isPartner(state: GameState, playerId: string): boolean {
  const me = state.me;
  const other = seatOf(state, playerId);
  return me !== null && other !== null && other.teamId === me.teamId && other.playerId !== me.playerId;
}

const HANDLERS: Partial<Record<FrameType, Handler>> = {
  /** The stream's opening frame: which seat this client is (§6.2). */
  stream_started: (state, p) => ({
    ...state,
    me: {
      playerId: p["player_id"] as string,
      seat: p["seat"] as SeatName,
      name: (p["you"] as { name: string }).name,
      type: (p["you"] as { type: "human" | "computer" }).type,
      teamId: teamOf(p["seat"] as SeatName),
    },
    partial: Boolean(p["partial"]),
  }),

  /** The table: seats, partnerships, and the score the game is played to. */
  game_configured: (state, p) => {
    const seats = (p["seats"] as SeatPayload[]).map((s) => ({
      playerId: s.player_id,
      name: s.name,
      type: s.type,
      seat: s.seat,
      teamId: teamOf(s.seat),
    }));
    return {
      ...state,
      seats,
      teams: (p["teams"] as { team_id: string; name: string }[]).map((t) => ({
        teamId: t.team_id,
        name: t.name,
        score: 0,
      })),
      winningScore: p["winning_score"] as number,
      handCounts: Object.fromEntries(seats.map((s) => [s.playerId, 0])),
    };
  },

  /** A fresh face-down spread, with nothing drawn from it yet (FR-11a). */
  dealer_selection_started: (state, p) => ({
    ...state,
    spreadSize: p["spread_size"] as number,
    draws: [],
    dealerPlayerId: null,
  }),

  /** One player's draw, turned face up (FR-11, FR-15). */
  draw_made: (state, p) => ({
    ...state,
    draws: [...state.draws, {
      playerId: p["player_id"] as string,
      position: p["position"] as number,
      card: p["card"] as CardCode,
    }],
  }),

  /** A tie: the whole selection is repeated with a new spread (FR-14). */
  draw_tied: (state) => ({ ...state, draws: [], dealerPlayerId: null }),

  dealer_selected: (state, p) => ({
    ...state,
    dealerPlayerId: p["dealer_player_id"] as string,
  }),

  /** A new deal. Clears everything that belongs to one round (FR-16). */
  round_started: (state, p) => ({
    ...clearRound(state),
    roundNumber: p["round_number"] as number,
    dealerPlayerId: p["dealer_player_id"] as string,
  }),

  /**
   * This seat's twelve cards, sent to nobody else (FR-21, FR-22, NFR-6).
   *
   * The other three hands are known only as counts, and every seat is dealt
   * the same number, so one private frame tells this client every count.
   */
  cards_dealt: (state, p) => {
    const cards = p["cards"] as CardCode[];
    return {
      ...state,
      hand: sortHand(cards, state.trump),
      handCounts: Object.fromEntries(state.seats.map((s) => [s.playerId, cards.length])),
    };
  },

  /** A bid or a pass, visible to everyone as it is made (FR-33). */
  bid_placed: (state, p) => ({
    ...state,
    bids: [...state.bids, {
      playerId: p["player_id"] as string,
      amount: p["amount"] as number | null,
    }],
    highBid: p["current_high"] as number,
  }),

  /** A lone bidder is offered the contract and may decline it (FR-32). */
  contract_offered: (state, p) => ({
    ...state,
    offer: { playerId: p["player_id"] as string, amount: p["amount"] as number },
  }),

  /** All passed, or the lone bidder declined: no score changes (FR-31). */
  round_abandoned: (state) => ({ ...clearRound(state) }),

  /** Trump is named, which re-sorts the hand (FR-36, FR-23a). */
  trump_named: (state, p) => {
    const trump = p["suit"] as SuitName;
    const winner = state.offer ?? lastBidder(state);
    return {
      ...state,
      trump,
      hand: sortHand(state.hand, trump),
      offer: null,
      contract: state.contract ?? winner,
    };
  },

  /**
   * The pass, sent to the passing team only (FR-38, FR-40, RT-1).
   *
   * Both partners receive the frame, so this seat may be either end of it.
   * Being neither means the frame is about the other partnership, and there
   * is nothing here this client is entitled to act on.
   */
  cards_passed: (state, p) => {
    const from = p["from_player_id"] as string;
    const to = p["to_player_id"] as string;
    const cards = p["cards"] as CardCode[];
    const me = state.me?.playerId;

    // Both counts move whichever end this seat is, or neither: four cards
    // leave one hand and join another, and UI-5 draws every hand at its true
    // size. Only the cards themselves are private.
    const handCounts = {
      ...state.handCounts,
      [from]: (state.handCounts[from] ?? 0) - cards.length,
      [to]: (state.handCounts[to] ?? 0) + cards.length,
    };

    if (me === from) {
      return {
        ...state,
        handCounts,
        sent: { toPlayerId: to, cards },
        hand: sortHand(cards.reduce(removeOne, state.hand), state.trump),
      };
    }
    if (me === to) {
      return {
        ...state,
        handCounts,
        received: { fromPlayerId: from, cards },
        hand: sortHand([...state.hand, ...cards], state.trump),
      };
    }
    return { ...state, handCounts };
  },

  /** A seat's meld, face up in front of them (FR-44, UI-13, UI-14a). */
  meld_exposed: (state, p) => {
    const playerId = p["player_id"] as string;
    const total = p["total"] as number;
    const seat = seatOf(state, playerId);
    const teamId = seat?.teamId;
    return {
      ...state,
      meld: {
        ...state.meld,
        [playerId]: { units: p["units"] as MeldUnit[], total },
      },
      teamMeld: teamId === undefined
        ? state.teamMeld
        : { ...state.teamMeld, [teamId]: (state.teamMeld[teamId] ?? 0) + total },
    };
  },

  /** Meld is over and the first trick may be led (FR-50a). */
  play_begun: (state, p) => ({
    ...state,
    leaderPlayerId: p["leader_player_id"] as string,
  }),

  /** The auction winner concedes rather than play the hand (FR-50b). */
  contract_tossed_in: (state, p) => ({
    ...state,
    tossedInBy: p["player_id"] as string,
  }),

  /** A seat is inside its move delay (RT-7, RT-10). */
  seat_thinking: (state, p) => ({
    ...state,
    thinkingPlayerId: p["player_id"] as string,
  }),

  /**
   * A card played (FR-57).
   *
   * If it is this seat's own card, one copy leaves the hand — one, because a
   * hand can hold both copies of a card.
   */
  card_played: (state, p) => {
    const playerId = p["player_id"] as string;
    const card = p["card"] as CardCode;
    const mine = playerId === state.me?.playerId;
    return {
      ...state,
      trick: [...state.trick, { playerId, card }],
      hand: mine ? removeOne(state.hand, card) : state.hand,
      handCounts: { ...state.handCounts, [playerId]: (state.handCounts[playerId] ?? 0) - 1 },
      thinkingPlayerId: null,
      prompt: mine ? null : state.prompt,
    };
  },

  /**
   * Four cards are down and a winner is known (FR-54, UI-15).
   *
   * The trick stays on the table: it is cleared by its own event, after a
   * pause the server owns and counts (RT-8).
   */
  trick_completed: (state, p) => ({
    ...state,
    trick: (p["cards"] as PlayPayload[]).map((c) => ({
      playerId: c.player_id,
      card: c.card,
    })),
    trickWinnerPlayerId: p["winner_player_id"] as string,
  }),

  /**
   * The trick is gathered to its winner (UI-15, RT-10).
   *
   * What it held becomes the last trick, reviewable until the next one is
   * cleared in its turn (UI-14b). Only the count is kept, never the points
   * those cards are worth (UI-14c).
   */
  trick_cleared: (state, p) => {
    const winnerPlayerId = p["winner_player_id"] as string;
    const teamId = seatOf(state, winnerPlayerId)?.teamId;
    return {
      ...state,
      lastTrick: { plays: state.trick, winnerPlayerId },
      trick: [],
      trickWinnerPlayerId: null,
      leaderPlayerId: p["next_leader_player_id"] as string,
      tricksTaken: teamId === undefined
        ? state.tricksTaken
        : { ...state.tricksTaken, [teamId]: (state.tricksTaken[teamId] ?? 0) + 1 },
    };
  },

  /** What this seat may do now, sent only to this seat (§6.5). */
  turn_prompt: (state, p) => ({ ...state, prompt: toPrompt(p) }),

  /**
   * The round's arithmetic, and the only place card points appear (FR-66).
   *
   * Cumulative scores are taken from here rather than accumulated, so the
   * client's totals are the server's and cannot drift.
   */
  round_scored: (state, p) => {
    const teams = (p["teams"] as TeamScorePayload[]).map((t) => ({
      teamId: t.team_id,
      meld: t.meld,
      cardPoints: t.card_points,
      lastTrickBonus: t.last_trick_bonus,
      roundTotal: t.round_total,
      pointsApplied: t.points_applied,
      cumulativeScore: t.cumulative_score,
    }));
    return {
      ...state,
      roundSummary: {
        roundNumber: p["round_number"] as number,
        bidTeamId: p["bid_team_id"] as string,
        bidWinnerPlayerId: p["bid_winner_player_id"] as string,
        contract: p["contract"] as number,
        madeContract: Boolean(p["made_contract"]),
        tossedIn: Boolean(p["tossed_in"]),
        teams,
      },
      teams: state.teams.map((team) => {
        const scored = teams.find((t) => t.teamId === team.teamId);
        return scored === undefined ? team : { ...team, score: scored.cumulativeScore };
      }),
      prompt: null,
    };
  },

  game_over: (state, p) => ({
    ...state,
    gameOver: {
      winningTeamId: p["winning_team_id"] as string,
      nsScore: p["ns_score"] as number,
      ewScore: p["ew_score"] as number,
    },
    prompt: null,
  }),

  // RT-12's transport frames. Handling them — telling the table a seat is
  // gone, and offering to abandon — is deliberately out of scope for this
  // release (docs/impl.md §6), so they are named here and change nothing,
  // rather than falling through an unwritten default.
  seat_lost: (state) => state,
  seat_rejoined: (state) => state,
  game_abandoned: (state) => state,
};

/** Shape of one seat inside the `game_configured` payload. */
interface SeatPayload {
  player_id: string;
  name: string;
  type: "human" | "computer";
  seat: SeatName;
}

/** Shape of one play inside the `trick_completed` payload. */
interface PlayPayload {
  player_id: string;
  card: CardCode;
}

/** Shape of one team inside the `round_scored` payload. */
interface TeamScorePayload {
  team_id: string;
  meld: number;
  card_points: number;
  last_trick_bonus: number;
  round_total: number;
  points_applied: number;
  cumulative_score: number;
}

/**
 * Clear what belongs to one round, keeping what belongs to the game.
 *
 * Cumulative scores, the table and the seats survive a deal; bids, meld,
 * trump, the trick and the hand do not. A round summary survives only until
 * the next round actually starts, so it can stay on screen while the players
 * read it.
 */
function clearRound(state: GameState): GameState {
  return {
    ...state,
    hand: [],
    handCounts: Object.fromEntries(state.seats.map((s) => [s.playerId, 0])),
    bids: [],
    highBid: 0,
    offer: null,
    contract: null,
    trump: null,
    received: null,
    sent: null,
    meld: {},
    teamMeld: {},
    leaderPlayerId: null,
    trick: [],
    trickWinnerPlayerId: null,
    lastTrick: null,
    tricksTaken: {},
    tossedInBy: null,
    thinkingPlayerId: null,
    prompt: null,
    roundSummary: null,
  };
}

/**
 * The seat that won the auction, for the case where no lone-bidder offer was
 * made: the last seat to have bid an amount (FR-30).
 */
function lastBidder(state: GameState): { playerId: string; amount: number } | null {
  for (let i = state.bids.length - 1; i >= 0; i -= 1) {
    const bid = state.bids[i];
    if (bid !== undefined && bid.amount !== null) {
      return { playerId: bid.playerId, amount: bid.amount };
    }
  }
  return null;
}

/** Convert a turn-prompt payload to its camel-cased form. */
function toPrompt(p: Record<string, unknown>): Prompt {
  const prompt: Prompt = { phase: p["phase"] as string };
  if ("minimum_bid" in p) prompt.minimumBid = p["minimum_bid"] as number;
  if ("may_pass" in p) prompt.mayPass = Boolean(p["may_pass"]);
  if ("amount" in p) prompt.amount = p["amount"] as number;
  if ("count" in p) prompt.count = p["count"] as number;
  if ("may_begin_play" in p) prompt.mayBeginPlay = Boolean(p["may_begin_play"]);
  if ("may_toss_in" in p) prompt.mayTossIn = Boolean(p["may_toss_in"]);
  if ("legal_plays" in p) prompt.legalPlays = p["legal_plays"] as CardCode[];
  return prompt;
}
