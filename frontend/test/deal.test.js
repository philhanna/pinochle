import { test } from "node:test";
import assert from "node:assert/strict";

import { DEAL_PACKET_COUNT, dealingView, dealOrder } from "../dist/deal.js";
import { applyEvent, initialState } from "../dist/state.js";
import { statusLine } from "../dist/view.js";

const TURN = { phase: "BIDDING", current_player_id: "p-east", paused: null, round_number: 1 };

function frame(type, payload) {
  return { seq: 1, type, turn: TURN, payload };
}

function dealt() {
  return [
    frame("stream_started", {
      seat: "SOUTH", player_id: "p-south", you: { name: "South", type: "human" }, partial: false,
    }),
    frame("game_configured", {
      seats: [
        { player_id: "p-north", name: "North", type: "human", seat: "NORTH" },
        { player_id: "p-east", name: "East", type: "human", seat: "EAST" },
        { player_id: "p-south", name: "South", type: "human", seat: "SOUTH" },
        { player_id: "p-west", name: "West", type: "human", seat: "WEST" },
      ],
      teams: [{ team_id: "NS", name: "Us" }, { team_id: "EW", name: "Them" }],
      winning_score: 2000,
    }),
    frame("round_started", { round_number: 1, dealer_player_id: "p-north" }),
    frame("cards_dealt", {
      cards: ["AS", "TS", "KS", "QS", "JS", "9S", "AH", "TH", "KH", "QH", "JH", "9H"],
    }),
  ].reduce(applyEvent, initialState());
}

test("the deal starts left of the dealer and proceeds clockwise", () => {
  assert.deepEqual(dealOrder(dealt()), ["p-east", "p-south", "p-west", "p-north"]);
});

test("the visible deal adds three cards to one seat at a time", () => {
  const state = dealt();
  assert.deepEqual(dealingView(state, 0).handCounts, {
    "p-north": 0, "p-east": 0, "p-south": 0, "p-west": 0,
  });
  assert.deepEqual(dealingView(state, 3).handCounts, {
    "p-north": 0, "p-east": 3, "p-south": 3, "p-west": 3,
  });
  assert.deepEqual(dealingView(state, 5).handCounts, {
    "p-north": 3, "p-east": 6, "p-south": 3, "p-west": 3,
  });
  assert.deepEqual(dealingView(state, DEAL_PACKET_COUNT).handCounts, {
    "p-north": 12, "p-east": 12, "p-south": 12, "p-west": 12,
  });
});

test("this seat's hand appears in matching three-card packets", () => {
  const state = dealt();
  assert.equal(dealingView(state, 1).hand.length, 0);
  assert.equal(dealingView(state, 2).hand.length, 3);
  assert.equal(dealingView(state, 6).hand.length, 6);
  assert.equal(dealingView(state, DEAL_PACKET_COUNT).hand.length, 12);
});

test("the projected deal suppresses actions and identifies what is happening", () => {
  const shown = dealingView(dealt(), 4);
  assert.equal(shown.prompt, null);
  assert.equal(shown.currentPlayerId, null);
  assert.equal(statusLine(shown), "Dealing the cards…");
});
