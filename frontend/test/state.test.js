// The reducer, frame type by frame type.
import { test } from "node:test";
import assert from "node:assert/strict";

import { applyEvent, initialState, isPartner, seatOf, teamOf } from "../dist/state.js";

const TURN = { phase: "BIDDING", current_player_id: "p-south", paused: null, round_number: 1 };

/** Build one frame, with a turn header that every real frame carries. */
function frame(type, payload, turn = TURN, seq = 1) {
  return { seq, type, turn, payload };
}

/** Fold a list of frames into a state, as a stream would. */
function replay(frames, state = initialState()) {
  return frames.reduce(applyEvent, state);
}

/** A state that has seen the stream open and the table configured. */
function seated(me = "p-south") {
  return replay([
    frame("stream_started", {
      seat: "SOUTH", player_id: me,
      you: { name: "Phil", type: "human" }, partial: false,
    }),
    frame("game_configured", {
      seats: [
        { player_id: "p-north", name: "N", type: "computer", seat: "NORTH" },
        { player_id: "p-east", name: "E", type: "computer", seat: "EAST" },
        { player_id: "p-south", name: "Phil", type: "human", seat: "SOUTH" },
        { player_id: "p-west", name: "W", type: "computer", seat: "WEST" },
      ],
      teams: [{ team_id: "NS", name: "Us" }, { team_id: "EW", name: "Them" }],
      winning_score: 2000,
    }),
  ]);
}

// ---------------------------------------------------------------------------
// Identity and the table
// ---------------------------------------------------------------------------

test("stream_started identifies this seat and derives its partnership", () => {
  const state = seated();
  assert.equal(state.me.playerId, "p-south");
  assert.equal(state.me.seat, "SOUTH");
  assert.equal(state.me.teamId, "NS");
  assert.equal(state.partial, false);
});

test("a resumed stream_started leaves what the client already knows (RT-5a)", () => {
  const before = replay([
    frame("bid_placed", { player_id: "p-south", amount: 250, current_high: 250 }),
  ], seated());

  const after = applyEvent(before, frame("stream_started", {
    seat: "SOUTH", player_id: "p-south",
    you: { name: "Phil", type: "human" }, partial: true, resume: "resumed",
  }, TURN, 0));

  // The reopened connection re-sends this frame; it must not undo the round.
  assert.equal(after.bids.length, 1);
  assert.equal(after.partial, false);
  assert.equal(after.me.playerId, "p-south");
});

test("a resume the server could not complete leaves the client partial (RT-5a)", () => {
  const after = applyEvent(seated(), frame("stream_started", {
    seat: "SOUTH", player_id: "p-south",
    you: { name: "Phil", type: "human" }, partial: false, resume: "incomplete",
  }, TURN, 0));

  assert.equal(after.partial, true);
});

test("partnerships are derived from the seat, never carried (FR-4a)", () => {
  assert.equal(teamOf("NORTH"), "NS");
  assert.equal(teamOf("SOUTH"), "NS");
  assert.equal(teamOf("EAST"), "EW");
  assert.equal(teamOf("WEST"), "EW");
});

test("game_configured seats all four players with their teams", () => {
  const state = seated();
  assert.equal(state.seats.length, 4);
  assert.equal(seatOf(state, "p-north").teamId, "NS");
  assert.equal(seatOf(state, "p-east").teamId, "EW");
  assert.equal(state.winningScore, 2000);
});

test("a partner is the other seat on this team", () => {
  const state = seated();
  assert.equal(isPartner(state, "p-north"), true);
  assert.equal(isPartner(state, "p-south"), false, "not one's own partner");
  assert.equal(isPartner(state, "p-east"), false);
});

// ---------------------------------------------------------------------------
// The deal (FR-21, FR-22, NFR-6, UI-5)
// ---------------------------------------------------------------------------

test("cards_dealt fills this hand and every seat's count", () => {
  const cards = ["AS", "TS", "KH", "QH", "JD", "9D", "AC", "TC", "KS", "QS", "JS", "9S"];
  const state = replay([frame("cards_dealt", { cards })], seated());
  assert.equal(state.hand.length, 12);
  assert.deepEqual(state.handCounts, {
    "p-north": 12, "p-east": 12, "p-south": 12, "p-west": 12,
  });
});

test("the dealt hand arrives in display order (FR-23)", () => {
  const state = replay([frame("cards_dealt", { cards: ["9C", "AD", "KH", "QS"] })], seated());
  assert.deepEqual(state.hand, ["QS", "KH", "9C", "AD"]);
});

// ---------------------------------------------------------------------------
// Bidding (FR-33, FR-32, UI-10, UI-14a)
// ---------------------------------------------------------------------------

test("bid_placed keeps the whole history, passes included", () => {
  const state = replay([
    frame("bid_placed", { player_id: "p-north", amount: 250, current_high: 250 }),
    frame("bid_placed", { player_id: "p-east", amount: null, current_high: 250 }),
    frame("bid_placed", { player_id: "p-south", amount: 260, current_high: 260 }),
  ], seated());
  assert.deepEqual(state.bids, [
    { playerId: "p-north", amount: 250 },
    { playerId: "p-east", amount: null },
    { playerId: "p-south", amount: 260 },
  ]);
  assert.equal(state.highBid, 260);
});

test("contract_offered records a lone bidder's offer until trump is named", () => {
  let state = replay([
    frame("bid_placed", { player_id: "p-south", amount: 250, current_high: 250 }),
    frame("contract_offered", { player_id: "p-south", amount: 250 }),
  ], seated());
  assert.deepEqual(state.offer, { playerId: "p-south", amount: 250 });

  state = applyEvent(state, frame("trump_named", { suit: "SPADES" }));
  assert.equal(state.offer, null);
  assert.deepEqual(state.contract, { playerId: "p-south", amount: 250 });
});

test("the contract falls to the last seat that bid when nobody was offered", () => {
  const state = replay([
    frame("bid_placed", { player_id: "p-north", amount: 250, current_high: 250 }),
    frame("bid_placed", { player_id: "p-east", amount: 260, current_high: 260 }),
    frame("bid_placed", { player_id: "p-south", amount: null, current_high: 260 }),
    frame("trump_named", { suit: "HEARTS" }),
  ], seated());
  assert.deepEqual(state.contract, { playerId: "p-east", amount: 260 });
});

test("trump_named re-sorts the hand with trump leftmost (FR-23a)", () => {
  const state = replay([
    frame("cards_dealt", { cards: ["9C", "AD", "KH", "QS"] }),
    frame("trump_named", { suit: "DIAMONDS" }),
  ], seated());
  assert.equal(state.trump, "DIAMONDS");
  assert.deepEqual(state.hand, ["AD", "QS", "KH", "9C"]);
});

// ---------------------------------------------------------------------------
// The pass (FR-38, FR-40, RT-1)
// ---------------------------------------------------------------------------

test("cards received from a partner join this hand", () => {
  const state = replay([
    frame("cards_dealt", { cards: ["9S", "9H", "9D", "9C"] }),
    frame("cards_passed", {
      from_player_id: "p-north", to_player_id: "p-south", cards: ["AS", "AH"],
    }),
  ], seated());
  assert.deepEqual(state.received, { fromPlayerId: "p-north", cards: ["AS", "AH"] });
  assert.equal(state.hand.length, 6);
  assert.equal(state.handCounts["p-south"], 6);
  assert.equal(state.handCounts["p-north"], 2);
});

test("cards sent to a partner leave this hand", () => {
  const state = replay([
    frame("cards_dealt", { cards: ["AS", "AH", "9D", "9C"] }),
    frame("cards_passed", {
      from_player_id: "p-south", to_player_id: "p-north", cards: ["AS", "AH"],
    }),
  ], seated());
  assert.deepEqual(state.sent, { toPlayerId: "p-north", cards: ["AS", "AH"] });
  assert.deepEqual(state.hand, ["9C", "9D"]);
  assert.equal(state.handCounts["p-south"], 2);
});

test("the other partnership's pass reveals nothing but counts", () => {
  const state = replay([
    frame("cards_dealt", { cards: ["AS", "AH", "9D", "9C"] }),
    frame("cards_passed", {
      from_player_id: "p-east", to_player_id: "p-west", cards: ["AS", "AH"],
    }),
  ], seated());
  assert.equal(state.received, null);
  assert.equal(state.sent, null);
  assert.deepEqual(state.hand, ["AS", "AH", "9C", "9D"]);
  assert.equal(state.handCounts["p-east"], 2);
  assert.equal(state.handCounts["p-west"], 6);
});

// ---------------------------------------------------------------------------
// Meld (FR-44, UI-13, UI-14a)
// ---------------------------------------------------------------------------

test("meld_exposed records each seat's units and accumulates team totals", () => {
  const state = replay([
    frame("meld_exposed", {
      player_id: "p-south", units: [{ name: "Pinochle", points: 40 }], total: 40,
    }),
    frame("meld_exposed", {
      player_id: "p-north", units: [{ name: "Marriage", points: 20 }], total: 20,
    }),
    frame("meld_exposed", {
      player_id: "p-east", units: [{ name: "Run", points: 150 }], total: 150,
    }),
  ], seated());
  assert.equal(state.meld["p-south"].total, 40);
  assert.deepEqual(state.teamMeld, { NS: 60, EW: 150 });
});

// ---------------------------------------------------------------------------
// Trick play (FR-54, FR-57, UI-14b, UI-15, RT-8)
// ---------------------------------------------------------------------------

test("playing a card removes one copy from this hand and the count", () => {
  const state = replay([
    frame("cards_dealt", { cards: ["TS", "TS", "AS"] }),
    frame("card_played", { player_id: "p-south", card: "TS" }),
  ], seated());
  assert.deepEqual(state.hand, ["AS", "TS"], "the second copy stays");
  assert.equal(state.handCounts["p-south"], 2);
  assert.deepEqual(state.trick, [{ playerId: "p-south", card: "TS" }]);
});

test("another seat's card touches the trick and their count, not this hand", () => {
  const state = replay([
    frame("cards_dealt", { cards: ["AS", "KS"] }),
    frame("card_played", { player_id: "p-west", card: "9C" }),
  ], seated());
  assert.deepEqual(state.hand, ["AS", "KS"]);
  assert.equal(state.handCounts["p-west"], 1);
  assert.equal(state.trick.length, 1);
});

test("a completed trick stays on the table until its own event clears it", () => {
  // RT-8, RT-10: the pause is the server's, delimited by events. The client
  // holds no timer and must not clear the trick itself.
  const state = replay([
    frame("trick_completed", {
      winner_player_id: "p-south",
      cards: [
        { player_id: "p-south", card: "AS" }, { player_id: "p-west", card: "9S" },
        { player_id: "p-north", card: "KS" }, { player_id: "p-east", card: "QS" },
      ],
    }),
  ], seated());
  assert.equal(state.trick.length, 4);
  assert.equal(state.trickWinnerPlayerId, "p-south");
  assert.equal(state.lastTrick, null);
});

test("clearing a trick makes it the reviewable last trick (UI-14b)", () => {
  const plays = [
    { player_id: "p-south", card: "AS" }, { player_id: "p-west", card: "9S" },
    { player_id: "p-north", card: "KS" }, { player_id: "p-east", card: "QS" },
  ];
  const state = replay([
    frame("trick_completed", { winner_player_id: "p-south", cards: plays }),
    frame("trick_cleared", {
      winner_player_id: "p-south", next_leader_player_id: "p-south",
    }),
  ], seated());
  assert.equal(state.trick.length, 0);
  assert.equal(state.trickWinnerPlayerId, null);
  assert.equal(state.lastTrick.winnerPlayerId, "p-south");
  assert.equal(state.lastTrick.plays.length, 4);
  assert.equal(state.leaderPlayerId, "p-south");
  assert.deepEqual(state.tricksTaken, { NS: 1 });
});

// ---------------------------------------------------------------------------
// Prompts (§6.5, UI-9)
// ---------------------------------------------------------------------------

test("turn_prompt carries what this seat may do, legal plays included", () => {
  const playing = { phase: "PLAYING", current_player_id: "p-south", paused: null, round_number: 1 };
  const state = replay([
    frame("turn_prompt", { phase: "PLAYING", legal_plays: ["AS", "KS"] }, playing),
  ], seated());
  assert.deepEqual(state.prompt, { phase: "PLAYING", legalPlays: ["AS", "KS"] });
});

test("a bidding prompt carries the minimum and whether passing is allowed", () => {
  const state = replay([
    frame("turn_prompt", { phase: "BIDDING", minimum_bid: 260, may_pass: true }),
  ], seated());
  assert.deepEqual(state.prompt, { phase: "BIDDING", minimumBid: 260, mayPass: true });
});

test("this seat's own play clears its prompt", () => {
  const state = replay([
    frame("cards_dealt", { cards: ["AS"] }),
    frame("turn_prompt", { phase: "PLAYING", legal_plays: ["AS"] }),
    frame("card_played", { player_id: "p-south", card: "AS" }),
  ], seated());
  assert.equal(state.prompt, null);
});

test("a prompt is dropped once the header moves past its phase (NFR-4)", () => {
  // The recorded case this guards: the auction winner keeps the turn
  // straight through passing, melding and into play, so the current player
  // never changes — only the phase does. Without watching the phase too, a
  // client would go on offering "Pass 4 cards" controls after the server has
  // moved on to melding, with nothing but a rejection to stop them being used.
  const passing = { phase: "PASSING", current_player_id: "p-south", paused: null, round_number: 1 };
  const melding = { phase: "MELDING", current_player_id: "p-south", paused: null, round_number: 1 };
  const state = replay([
    frame("turn_prompt", { phase: "PASSING", count: 4 }, passing),
    frame("seat_thinking", { player_id: "p-south" }, melding),
  ], seated());
  assert.equal(state.prompt, null);
});

test("a live prompt survives frames that do not touch it", () => {
  // The common case: unrelated frames — another seat thinking, and so on —
  // must not be mistaken for the phase having moved on.
  const playing = { phase: "PLAYING", current_player_id: "p-south", paused: null, round_number: 1 };
  const state = replay([
    frame("turn_prompt", { phase: "PLAYING", legal_plays: ["AS"] }, playing),
    frame("seat_thinking", { player_id: "p-north" }, playing),
  ], seated());
  assert.deepEqual(state.prompt, { phase: "PLAYING", legalPlays: ["AS"] });
});

// ---------------------------------------------------------------------------
// Round and game boundaries (FR-16, FR-31, FR-66, FR-71)
// ---------------------------------------------------------------------------

test("a new round clears the round but keeps the game", () => {
  const before = replay([
    frame("cards_dealt", { cards: ["AS", "KS"] }),
    frame("bid_placed", { player_id: "p-south", amount: 250, current_high: 250 }),
    frame("trump_named", { suit: "SPADES" }),
    frame("meld_exposed", { player_id: "p-south", units: [], total: 40 }),
  ], seated());

  const after = applyEvent(before, frame("round_started", {
    round_number: 2, dealer_player_id: "p-east",
  }));

  assert.equal(after.roundNumber, 2);
  assert.deepEqual(after.hand, []);
  assert.deepEqual(after.bids, []);
  assert.equal(after.trump, null);
  assert.deepEqual(after.teamMeld, {});
  assert.equal(after.seats.length, 4, "the table survives a deal");
  assert.equal(after.winningScore, 2000);
});

test("an abandoned round changes no score (FR-31)", () => {
  const state = replay([
    frame("bid_placed", { player_id: "p-south", amount: null, current_high: 0 }),
    frame("round_abandoned", { declined_by: null }),
  ], seated());
  assert.deepEqual(state.bids, []);
  assert.deepEqual(state.teams.map((t) => t.score), [0, 0]);
});

test("round_scored is where card points appear, and sets the totals (FR-66)", () => {
  const state = replay([
    frame("round_scored", {
      round_number: 1, bid_team_id: "NS", bid_winner_player_id: "p-south",
      contract: 250, made_contract: true, tossed_in: false,
      teams: [
        {
          team_id: "NS", meld: 90, card_points: 160, last_trick_bonus: 10,
          round_total: 260, points_applied: 260, cumulative_score: 260,
        },
        {
          team_id: "EW", meld: 40, card_points: 80, last_trick_bonus: 0,
          round_total: 120, points_applied: 120, cumulative_score: 120,
        },
      ],
    }),
  ], seated());
  assert.equal(state.roundSummary.madeContract, true);
  assert.equal(state.roundSummary.teams[0].cardPoints, 160);
  assert.deepEqual(state.teams.map((t) => t.score), [260, 120]);
});

test("game_over records the winner and the final scores", () => {
  const state = replay([
    frame("game_over", { winning_team_id: "NS", ns_score: 2050, ew_score: 1880 }),
  ], seated());
  assert.deepEqual(state.gameOver, {
    winningTeamId: "NS", nsScore: 2050, ewScore: 1880,
  });
});

// ---------------------------------------------------------------------------
// The turn header, and what the reducer refuses to know
// ---------------------------------------------------------------------------

test("every frame refreshes phase, turn and pause (RT-8, RT-10)", () => {
  const state = replay([
    frame("seat_thinking", { player_id: "p-west" }, {
      phase: "PLAYING", current_player_id: "p-west", paused: "thinking", round_number: 3,
    }),
  ], seated());
  assert.equal(state.phase, "PLAYING");
  assert.equal(state.currentPlayerId, "p-west");
  assert.equal(state.paused, "thinking");
  assert.equal(state.thinkingPlayerId, "p-west");
});

test("a gap in sequence numbers is normal and changes nothing", () => {
  // The frames addressed to other seats consume numbers, so this seat sees
  // 14 then 17. A client that waited for 15 would wait forever.
  const state = replay([
    frame("round_started", { round_number: 1, dealer_player_id: "p-east" }, TURN, 14),
    frame("cards_dealt", { cards: ["AS"] }, TURN, 17),
  ], seated());
  assert.equal(state.lastSeq, 17);
  assert.equal(state.hand.length, 1);
});

test("the transport's seat frames are accepted and ignored (impl.md §6)", () => {
  const before = seated();
  const after = replay([
    frame("seat_lost", { player_id: "p-west" }),
    frame("seat_rejoined", { player_id: "p-west" }),
    frame("game_abandoned", { reason: "operator" }),
  ], before);
  assert.deepEqual({ ...after, lastSeq: 0 }, { ...before, lastSeq: 0 });
});

test("an unknown frame type is ignored rather than throwing", () => {
  const state = replay([frame("something_new", { whatever: 1 })], seated());
  assert.equal(state.seats.length, 4);
});

test("applyEvent does not mutate the state it is given", () => {
  const before = seated();
  const handBefore = before.hand;
  applyEvent(before, frame("cards_dealt", { cards: ["AS", "KS"] }));
  assert.equal(before.hand, handBefore);
  assert.deepEqual(before.hand, []);
});

// ---------------------------------------------------------------------------
// The console's credential (§5.1)
// ---------------------------------------------------------------------------

test("the console takes its admin token from the URL when one is there", async () => {
  const { resolveAdminToken } = await import("../dist/token.js");
  const store = new Map();
  globalThis.window = {
    sessionStorage: {
      getItem: (k) => store.get(k) ?? null,
      setItem: (k, v) => store.set(k, v),
    },
  };

  assert.equal(resolveAdminToken(new URL("http://x/admin?t=dev")), "dev");
  // …and remembers it, so a reload does not ask again.
  assert.equal(resolveAdminToken(new URL("http://x/admin")), "dev");
  delete globalThis.window;
});

test("the console has no token when neither the URL nor the tab has one", async () => {
  const { resolveAdminToken } = await import("../dist/token.js");
  globalThis.window = {
    sessionStorage: { getItem: () => null, setItem: () => {} },
  };
  assert.equal(resolveAdminToken(new URL("http://x/admin")), "");
  delete globalThis.window;
});
