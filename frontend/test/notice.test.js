// The one sentence the table is being told (UI-19).
import { test } from "node:test";
import assert from "node:assert/strict";

import { notice } from "../dist/notice.js";
import { applyEvent, initialState } from "../dist/state.js";

const TURN = { phase: "PLAYING", current_player_id: "p-south", paused: null, round_number: 2 };

function frame(type, payload, turn = TURN) {
  return { seq: 1, type, turn, payload };
}

/** A turn header carrying a hold the server has named (RT-13). */
function holding(hold, phase = "PLAYING") {
  return { phase, current_player_id: null, paused: null, hold, round_number: 2 };
}

function seated() {
  return [
    frame("stream_started", {
      seat: "SOUTH", player_id: "p-south", you: { name: "Phil", type: "human" }, partial: false,
    }),
    frame("game_configured", {
      seats: [
        { player_id: "p-north", name: "North", type: "computer", seat: "NORTH" },
        { player_id: "p-east", name: "East", type: "computer", seat: "EAST" },
        { player_id: "p-south", name: "Phil", type: "human", seat: "SOUTH" },
        { player_id: "p-west", name: "West", type: "computer", seat: "WEST" },
      ],
      teams: [{ team_id: "NS", name: "Us" }, { team_id: "EW", name: "Them" }],
      winning_score: 2000,
    }),
  ].reduce(applyEvent, initialState());
}

test("a table that has not started yet has nothing to say", () => {
  assert.equal(notice(seated()), null);
});

test("the draw's outcome names the dealer (FR-13)", () => {
  const state = applyEvent(seated(), frame("dealer_selected", { dealer_player_id: "p-east" }));
  assert.equal(notice(state).text, "East deals.");
});

test("the auction's outcome stands until trump is named (FR-30)", () => {
  const state = [
    frame("bid_placed", { player_id: "p-east", amount: 260, current_high: 260 }),
    frame("contract_offered", { player_id: "p-east", amount: 260 }),
    frame("trump_named", { suit: "HEARTS" }),
  ].reduce(applyEvent, seated());
  assert.equal(notice(state).text, "East plays 260 in ♥ hearts.");
});

test("a contract without trump yet says only that the auction is won", () => {
  const state = [
    frame("bid_placed", { player_id: "p-east", amount: 260, current_high: 260 }),
    frame("contract_offered", { player_id: "p-east", amount: 260 }),
  ].reduce(applyEvent, seated());
  assert.match(notice(state).text, /East bid 260 alone/);
});

test("a completed trick names its winner while the table holds (UI-15, UI-19)", () => {
  // The server has not been taught to name its holds yet; the older `paused`
  // field still has to produce a notice.
  const paused = { ...TURN, current_player_id: null, paused: "trick_clear" };
  const state = [
    frame("trick_completed", {
      winner_player_id: "p-west",
      cards: [{ player_id: "p-west", card: "AS" }],
    }, paused),
  ].reduce(applyEvent, seated());

  const shown = notice(state);
  assert.equal(shown.text, "West takes the trick.");
  assert.equal(shown.kind, "hold");
  assert.equal(shown.release, null, "a timed hold offers nothing to click");
});

test("a seat's move delay is a hold like any other (RT-7, RT-9)", () => {
  const paused = { ...TURN, current_player_id: "p-north", paused: "thinking" };
  const state = applyEvent(seated(), frame("seat_thinking", { player_id: "p-north" }, paused));
  assert.equal(notice(state).text, "North is thinking…");
});

test("a hold awaiting release carries the id to release (UI-19a, RT-13)", () => {
  const hold = { id: 41, reason: "round_scored", ackable: true };
  const state = applyEvent(seated(), frame("round_scored", {
    round_number: 2,
    bid_team_id: "EW",
    bid_winner_player_id: "p-east",
    contract: 260,
    made_contract: true,
    tossed_in: false,
    teams: [],
  }, holding(hold, "SCORING")));

  const shown = notice(state);
  assert.equal(shown.text, "Round 2: East made the 260 contract.");
  assert.equal(shown.release, 41);
});

test("the last round is read before the winner is announced (FR-66, FR-71)", () => {
  const hold = { id: 41, reason: "round_scored", ackable: true };
  const scored = applyEvent(seated(), frame("round_scored", {
    round_number: 7,
    bid_team_id: "NS",
    bid_winner_player_id: "p-south",
    contract: 300,
    made_contract: true,
    tossed_in: false,
    teams: [],
  }, holding(hold, "SCORING")));

  // The round that ends the game is summarised and held like any other.
  const recap = notice(scored);
  assert.equal(recap.text, "Round 7: Phil made the 300 contract.");
  assert.equal(recap.release, 41);

  const over = [
    frame("hold_ended", { hold_id: 41, reason: "round_scored" }, holding(null, "SCORING")),
    frame("game_over", { winning_team_id: "NS", ns_score: 2010, ew_score: 1240 }, {
      phase: "FINISHED", current_player_id: null, paused: null, hold: null, round_number: 7,
    }),
  ].reduce(applyEvent, scored);

  const shown = notice(over);
  assert.equal(shown.kind, "final");
  assert.equal(shown.text, "Us team wins, 2010 to 1240.");
});

test("exposed meld waits for a Continue click", () => {
  const hold = { id: 42, reason: "meld_exposed", ackable: true };
  const state = applyEvent(seated(), frame("hold_begun", {
    hold_id: 42, reason: "meld_exposed", seconds: null, ackable: true,
  }, holding(hold, "MELDING")));

  const shown = notice(state);
  assert.equal(shown.text, "Review the meld laid out on the table.");
  assert.equal(shown.release, 42);
});

test("any seat sees the same release control, not just the one on the clock", () => {
  // RT-13 lets any one seat release a hold, so nothing here may depend on
  // whose turn it was when the hold began.
  const hold = { id: 41, reason: "round_scored", ackable: true };
  const north = applyEvent(seated(), frame("round_scored", {
    round_number: 2, bid_team_id: "EW", bid_winner_player_id: "p-north",
    contract: 260, made_contract: false, tossed_in: false, teams: [],
  }, holding(hold, "SCORING")));
  assert.equal(notice(north).release, 41);
});

test("a reason this client does not know still shows its control", () => {
  // Better an unnamed pause than a table that has silently stopped.
  const hold = { id: 77, reason: "something_new", ackable: true };
  const state = applyEvent(seated(), frame("card_played", {
    player_id: "p-east", card: "AS",
  }, holding(hold)));

  const shown = notice(state);
  assert.equal(shown.text, "The game is paused.");
  assert.equal(shown.release, 77);
});

test("a timed hold never offers a control, whatever its reason (UI-19a)", () => {
  const hold = { id: 12, reason: "dealer_selected", ackable: false };
  const state = applyEvent(
    seated(), frame("dealer_selected", { dealer_player_id: "p-west" }, holding(hold, "DEALING")),
  );
  assert.equal(notice(state).release, null);
});

test("the last trick stands as the notice until something else concludes", () => {
  const state = [
    frame("trick_completed", {
      winner_player_id: "p-west", cards: [{ player_id: "p-west", card: "AS" }],
    }),
    frame("trick_cleared", { winner_player_id: "p-west", next_leader_player_id: "p-west" }),
    frame("card_played", { player_id: "p-west", card: "KS" }),
  ].reduce(applyEvent, seated());
  assert.equal(notice(state).text, "West took the last trick.");
});

test("the key is unchanged by a frame that does not change the notice", () => {
  const base = applyEvent(seated(), frame("dealer_selected", { dealer_player_id: "p-east" }));
  const later = applyEvent(base, frame("cards_dealt", { cards: ["AS", "KS"] }));
  assert.equal(notice(base).key, notice(later).key);
});

test("the key changes from one trick to the next", () => {
  const paused = { ...TURN, current_player_id: null, paused: "trick_clear" };
  const first = applyEvent(seated(), frame("trick_completed", {
    winner_player_id: "p-west", cards: [{ player_id: "p-west", card: "AS" }],
  }, paused));
  const second = [
    frame("trick_cleared", { winner_player_id: "p-west", next_leader_player_id: "p-west" }),
    frame("trick_completed", {
      winner_player_id: "p-west", cards: [{ player_id: "p-west", card: "KS" }],
    }, paused),
  ].reduce(applyEvent, first);

  assert.notEqual(notice(first).key, notice(second).key);
});

test("the game's result outranks any hold still standing (FR-71)", () => {
  const hold = { id: 41, reason: "round_scored", ackable: true };
  const state = applyEvent(seated(), frame("game_over", {
    winning_team_id: "NS", ns_score: 2010, ew_score: 1240,
  }, holding(hold, "FINISHED")));

  const shown = notice(state);
  assert.equal(shown.kind, "final");
  assert.equal(shown.text, "Us team wins, 2010 to 1240.");
});

test("the deal's announcement ends when the first card is led (UI-19)", () => {
  const before = [
    frame("dealer_selected", { dealer_player_id: "p-east" }),
    frame("bid_placed", { player_id: "p-east", amount: 260, current_high: 260 }),
    frame("trump_named", { suit: "HEARTS" }),
  ].reduce(applyEvent, seated());
  assert.equal(before.trick.length, 0);
  assert.equal(notice(before).text, "East plays 260 in ♥ hearts.");

  const led = applyEvent(before, frame("card_played", { player_id: "p-east", card: "AH" }));
  assert.equal(
    notice(led), null,
    "who deals and what the contract is are both on the table by then",
  );
});

test("a trick taken is still announced once play is under way", () => {
  // Only the announcements from before the cards were led are retired: the
  // trick is the next thing to conclude, and UI-19 wants it said.
  const state = [
    frame("dealer_selected", { dealer_player_id: "p-east" }),
    frame("card_played", { player_id: "p-east", card: "AH" }),
    frame("trick_completed", {
      winner_player_id: "p-west", cards: [{ player_id: "p-east", card: "AH" }],
    }),
    frame("trick_cleared", { winner_player_id: "p-west", next_leader_player_id: "p-west" }),
  ].reduce(applyEvent, seated());
  assert.equal(notice(state).text, "West took the last trick.");
});

test("the round's hold says something before the summary arrives (UI-19a)", () => {
  // The hold is on the header of the frame that gathers the last trick, one
  // frame ahead of round_scored: a band with nothing in it but the button is
  // not what the player is being held for.
  const hold = { id: 9, reason: "round_scored", ackable: true };
  const state = applyEvent(seated(), frame(
    "trick_cleared",
    { winner_player_id: "p-west", next_leader_player_id: "p-west" },
    holding(hold, "SCORING"),
  ));

  const shown = notice(state);
  assert.equal(shown.text, "The round is over.");
  assert.equal(shown.release, 9);
});
