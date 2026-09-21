// The words on the table.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  bidCall, bidHistory, contractText, gameOverText, meldIsExposed, meldLines, scoreboard,
  seatLabel, statusLine, summaryHeadline, summaryRows, trumpText, winningBidText,
} from "../dist/view.js";
import { notice } from "../dist/notice.js";
import { applyEvent, initialState } from "../dist/state.js";

const TURN = { phase: "BIDDING", current_player_id: "p-south", paused: null, round_number: 2 };

function frame(type, payload, turn = TURN) {
  return { seq: 1, type, turn, payload };
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

test("the scoreboard shows both scores, the round, contract and trump (UI-14)", () => {
  const lines = scoreboard(seated());
  const labels = lines.map((line) => line.label);
  assert.deepEqual(labels, ["Us", "Them", "Round", "Contract", "Trump", "Playing to"]);
  assert.equal(lines[0].value, "0");
  assert.equal(lines[5].value, "2000");
});

test("a team's meld total rides along with its score all round (UI-14a)", () => {
  const state = [
    frame("meld_exposed", { player_id: "p-south", units: [], total: 40 }),
    frame("meld_exposed", { player_id: "p-north", units: [], total: 20 }),
  ].reduce(applyEvent, seated());
  assert.equal(scoreboard(state)[0].value, "0  (+60 meld)");
});

test("the meld total survives the cards being gathered up (UI-14a)", () => {
  // Exposed meld leaves the table when play starts; the total must not.
  const state = [
    frame("meld_exposed", { player_id: "p-south", units: [], total: 40 }),
    frame("play_begun", { leader_player_id: "p-south" }),
    frame("card_played", { player_id: "p-south", card: "AS" }),
  ].reduce(applyEvent, seated());
  assert.equal(scoreboard(state)[0].value, "0  (+40 meld)");
});

test("there is no card-point line anywhere on the scoreboard (UI-14c)", () => {
  const state = [
    frame("trick_completed", {
      winner_player_id: "p-south",
      cards: [{ player_id: "p-south", card: "AS" }],
    }),
    frame("trick_cleared", { winner_player_id: "p-south", next_leader_player_id: "p-south" }),
  ].reduce(applyEvent, seated());
  const text = JSON.stringify(scoreboard(state)).toLowerCase();
  assert.ok(!text.includes("point"), "counting the cards is the player's job");
});

test("the contract names its holder once trump is named", () => {
  const state = [
    frame("bid_placed", { player_id: "p-east", amount: 260, current_high: 260 }),
    frame("trump_named", { suit: "HEARTS" }),
  ].reduce(applyEvent, seated());
  assert.equal(contractText(state), "260 — East");
  assert.equal(trumpText(state), "♥ Hearts");
});

test("an offered contract is shown as offered until it is accepted (FR-32)", () => {
  const state = applyEvent(
    seated(), frame("contract_offered", { player_id: "p-south", amount: 250 }),
  );
  assert.equal(contractText(state), "250 offered");
  assert.equal(winningBidText(state), "Phil — 250");
});

test("the lower-left plaque shows the winner when the auction reaches trump", () => {
  const trumpTurn = { ...TURN, phase: "TRUMP", current_player_id: "p-north" };
  const state = [
    frame("bid_placed", { player_id: "p-north", amount: 270, current_high: 270 }),
    frame("bid_placed", { player_id: "p-east", amount: null, current_high: 270 }, trumpTurn),
  ].reduce(applyEvent, seated());
  assert.equal(winningBidText(state), "North — 270");
});

test("the auction plaque remains after trump is named", () => {
  const state = [
    frame("bid_placed", { player_id: "p-east", amount: 300, current_high: 300 }),
    frame("trump_named", { suit: "DIAMONDS" }),
  ].reduce(applyEvent, seated());
  assert.equal(winningBidText(state), "East — 300");
});

test("the bid history keeps every bid and pass in order (UI-10, UI-14a)", () => {
  const state = [
    frame("bid_placed", { player_id: "p-north", amount: 250, current_high: 250 }),
    frame("bid_placed", { player_id: "p-east", amount: null, current_high: 250 }),
  ].reduce(applyEvent, seated());
  assert.deepEqual(bidHistory(state), ["North: 250", "East: pass"]);
});

test("each hand shows that player's latest bid or pass", () => {
  const state = [
    frame("bid_placed", { player_id: "p-north", amount: 250, current_high: 250 }),
    frame("bid_placed", { player_id: "p-east", amount: null, current_high: 250 }),
    frame("bid_placed", { player_id: "p-north", amount: 270, current_high: 270 }),
  ].reduce(applyEvent, seated());
  assert.equal(bidCall(state, "p-north"), "270");
  assert.equal(bidCall(state, "p-east"), "pass");
  assert.equal(bidCall(state, "p-south"), null);
});

test("the calls beside the hands clear once trump is named", () => {
  const state = [
    frame("bid_placed", { player_id: "p-north", amount: 250, current_high: 250 }),
    frame("trump_named", { suit: "SPADES" }),
  ].reduce(applyEvent, seated());
  assert.equal(bidCall(state, "p-north"), null);
});

test("meld lines name each seat and its combinations (UI-13)", () => {
  const state = applyEvent(seated(), frame("meld_exposed", {
    player_id: "p-south",
    units: [{ name: "Pinochle", points: 40 }, { name: "Marriage", points: 20 }],
    total: 60,
  }));
  assert.deepEqual(meldLines(state), [{
    playerId: "p-south",
    name: "Phil",
    units: ["Pinochle 40", "Marriage 20"],
    total: 60,
  }]);
});

test("the round summary reports the contract's fate (FR-66)", () => {
  const made = applyEvent(seated(), frame("round_scored", {
    round_number: 4, bid_team_id: "NS", bid_winner_player_id: "p-south",
    contract: 260, made_contract: true, tossed_in: false,
    teams: [
      { team_id: "NS", meld: 90, card_points: 170, last_trick_bonus: 10,
        round_total: 270, points_applied: 270, cumulative_score: 270 },
      { team_id: "EW", meld: 30, card_points: 70, last_trick_bonus: 0,
        round_total: 100, points_applied: 100, cumulative_score: 100 },
    ],
  }));
  assert.equal(summaryHeadline(made), "Round 4: Phil made the 260 contract.");
  const rows = summaryRows(made);
  assert.equal(rows[0].bid, true);
  assert.equal(rows[0].cardPoints, 170);
  assert.equal(rows[1].bid, false);
});

test("going set and tossing in read differently (FR-50b, FR-66)", () => {
  const base = {
    round_number: 1, bid_team_id: "NS", bid_winner_player_id: "p-south",
    contract: 300, teams: [],
  };
  const set = applyEvent(seated(), frame("round_scored", {
    ...base, made_contract: false, tossed_in: false,
  }));
  assert.equal(summaryHeadline(set), "Round 1: Phil went set on the 300 contract.");

  const tossed = applyEvent(seated(), frame("round_scored", {
    ...base, made_contract: false, tossed_in: true,
  }));
  assert.equal(summaryHeadline(tossed), "Round 1: Phil tossed in the 300 contract.");
});

test("the status line says whose turn it is and what for (UI-7)", () => {
  assert.equal(statusLine(seated()), "Your turn — bidding");

  const theirs = applyEvent(seated(), frame("bid_placed", {
    player_id: "p-south", amount: 250, current_high: 250,
  }, { phase: "BIDDING", current_player_id: "p-west", paused: null, round_number: 2 }));
  assert.equal(statusLine(theirs), "West's turn — bidding");
});

test("a pause belongs to the notice, not the status line (UI-19, RT-9)", () => {
  // Both lines are on screen at once, so a pause reported in both would have
  // them paraphrasing each other. The notice says what the table is held for;
  // the status line says only whose turn it is.
  const clearing = applyEvent(seated(), frame("trick_completed", {
    winner_player_id: "p-south", cards: [],
  }, { phase: "PLAYING", current_player_id: null, paused: "trick_clear", round_number: 2 }));
  assert.equal(notice(clearing).text, "Phil takes the trick.");
  assert.equal(statusLine(clearing), "");

  const thinking = applyEvent(seated(), frame("seat_thinking", {
    player_id: "p-west",
  }, { phase: "PLAYING", current_player_id: "p-west", paused: "thinking", round_number: 2 }));
  assert.equal(notice(thinking).text, "West is thinking…");
  assert.equal(statusLine(thinking), "West's turn — play a card");
});

test("the game's result replaces the status line (FR-71)", () => {
  const state = applyEvent(seated(), frame("game_over", {
    winning_team_id: "EW", ns_score: 1920, ew_score: 2030,
  }));
  assert.equal(gameOverText(state), "Them team wins, 1920 to 2030.");
  assert.equal(statusLine(state), "Them team wins, 1920 to 2030.");
});

test("the dealer is marked at their seat (UI-3)", () => {
  const state = applyEvent(seated(), frame("dealer_selected", { dealer_player_id: "p-east" }));
  const east = state.seats.find((seat) => seat.playerId === "p-east");
  assert.equal(seatLabel(state, east), "East (dealer)");
  const south = state.seats.find((seat) => seat.playerId === "p-south");
  assert.equal(seatLabel(state, south), "Phil");
});

test("the meld is exposed until the first trick is gathered (UI-13, UI-14a)", () => {
  // What a seat showed is public while its cards are face-up; afterwards the
  // scoreboard keeps the totals and lets the named combinations go.
  const melded = applyEvent(seated(), frame("meld_exposed", {
    player_id: "p-south", units: [{ name: "Marriage", points: 20 }], total: 20,
  }));
  assert.equal(meldIsExposed(melded), true);

  const played = [
    frame("play_begun", { leader_player_id: "p-south" }),
    frame("card_played", { player_id: "p-south", card: "AS" }),
  ].reduce(applyEvent, melded);
  assert.equal(meldIsExposed(played), true, "still on the table during the first trick");

  const completed = applyEvent(played, frame("trick_completed", {
    winner_player_id: "p-south", cards: [{ player_id: "p-south", card: "AS" }],
  }));
  assert.equal(meldIsExposed(completed), true, "and while the trick lies there won");

  const gathered = applyEvent(completed, frame("trick_cleared", {
    winner_player_id: "p-south", next_leader_player_id: "p-south",
  }));
  assert.equal(meldIsExposed(gathered), false);
  assert.equal(meldLines(gathered)[0].total, 20, "but the total stays");
});
