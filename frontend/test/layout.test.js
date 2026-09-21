// Where seats and cards are placed, and what may be done with them.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  fanAngles, isLegalPlay, isMyTurn, minimumBid, mustDraw, passCount, placement,
  playHasBegun, scatter, spotOf, takenPositions, trickCards,
} from "../dist/layout.js";
import { applyEvent, initialState } from "../dist/state.js";

const TURN = { phase: "PLAYING", current_player_id: "p-south", paused: null, round_number: 1 };

function frame(type, payload, turn = TURN) {
  return { seq: 1, type, turn, payload };
}

/** A state seated as `seat`, with the table configured. */
function seated(seat = "SOUTH") {
  const me = `p-${seat.toLowerCase()}`;
  return [
    frame("stream_started", {
      seat, player_id: me, you: { name: "Me", type: "human" }, partial: false,
    }),
    frame("game_configured", {
      seats: [
        { player_id: "p-north", name: "North", type: "computer", seat: "NORTH" },
        { player_id: "p-east", name: "East", type: "computer", seat: "EAST" },
        { player_id: "p-south", name: "South", type: "human", seat: "SOUTH" },
        { player_id: "p-west", name: "West", type: "computer", seat: "WEST" },
      ],
      teams: [{ team_id: "NS", name: "Us" }, { team_id: "EW", name: "Them" }],
      winning_score: 2000,
    }),
  ].reduce(applyEvent, initialState());
}

// ---------------------------------------------------------------------------
// Seat placement (UI-1)
// ---------------------------------------------------------------------------

test("the viewer sits at the bottom, whichever seat they hold", () => {
  for (const seat of ["NORTH", "EAST", "SOUTH", "WEST"]) {
    const spots = placement(seated(seat));
    assert.equal(spots.bottom.seat, seat, `${seat} should be at the bottom`);
  }
});

test("the seat that plays next sits to the left (UI-1)", () => {
  // FR-3's turn order is clockwise N -> E -> S -> W, and at a table that means
  // play passes to the player on your left.
  const spots = placement(seated("SOUTH"));
  assert.equal(spots.left.seat, "WEST");
  assert.equal(spots.top.seat, "NORTH");
  assert.equal(spots.right.seat, "EAST");
});

test("the partner always sits across", () => {
  for (const seat of ["NORTH", "EAST", "SOUTH", "WEST"]) {
    const spots = placement(seated(seat));
    assert.equal(
      spots.top.teamId, spots.bottom.teamId,
      `${seat}'s partner should be across the table`,
    );
    assert.notEqual(spots.left.teamId, spots.bottom.teamId);
    assert.notEqual(spots.right.teamId, spots.bottom.teamId);
  }
});

test("the opponents sit left and right", () => {
  const spots = placement(seated("EAST"));
  assert.equal(spots.left.teamId, "NS");
  assert.equal(spots.right.teamId, "NS");
  assert.equal(spots.top.teamId, "EW");
});

test("an unseated client places nobody", () => {
  const spots = placement(initialState());
  assert.deepEqual(spots, { bottom: null, left: null, top: null, right: null });
});

test("spotOf finds where a seat is drawn", () => {
  const state = seated("SOUTH");
  assert.equal(spotOf(state, "p-south"), "bottom");
  assert.equal(spotOf(state, "p-west"), "left");
  assert.equal(spotOf(state, "p-nobody"), null);
});

// ---------------------------------------------------------------------------
// The trick (UI-6)
// ---------------------------------------------------------------------------

test("each played card is tagged with the seat that played it (UI-6)", () => {
  const state = [
    frame("card_played", { player_id: "p-south", card: "AS" }),
    frame("card_played", { player_id: "p-west", card: "9S" }),
  ].reduce(applyEvent, seated("SOUTH"));

  assert.deepEqual(trickCards(state), [
    { playerId: "p-south", card: "AS", spot: "bottom" },
    { playerId: "p-west", card: "9S", spot: "left" },
  ]);
});

test("a card from a seat that is not at the table is dropped, not drawn wrongly", () => {
  const state = applyEvent(seated(), frame("card_played", { player_id: "ghost", card: "AS" }));
  assert.deepEqual(trickCards(state), []);
});

// ---------------------------------------------------------------------------
// Legality (UI-9, ARC-2)
// ---------------------------------------------------------------------------

test("only the cards the server named are playable (UI-9)", () => {
  const state = applyEvent(
    seated(),
    frame("turn_prompt", { phase: "PLAYING", legal_plays: ["AS", "KS"] }),
  );
  assert.equal(isLegalPlay(state, "AS"), true);
  assert.equal(isLegalPlay(state, "9C"), false);
});

test("nothing is playable when it is not this seat's turn", () => {
  // No prompt means no turn: the client must not guess at legality (ARC-2).
  assert.equal(isLegalPlay(seated(), "AS"), false);
});

test("a prompt for another phase makes no card playable", () => {
  const passing = { phase: "PASSING", current_player_id: "p-south", paused: null, round_number: 1 };
  const state = applyEvent(
    seated(), frame("turn_prompt", { phase: "PASSING", count: 4 }, passing),
  );
  assert.equal(isLegalPlay(state, "AS"), false);
  assert.equal(passCount(state), 4);
});

test("isMyTurn follows the turn header", () => {
  assert.equal(isMyTurn(seated("SOUTH")), true);
  assert.equal(isMyTurn(seated("NORTH")), false);
});

// ---------------------------------------------------------------------------
// Drawing for the deal (FR-11, FR-11a)
// ---------------------------------------------------------------------------

test("a seat must draw until it has drawn", () => {
  const selection = { phase: "DEALER_SELECTION", current_player_id: null, paused: null, round_number: 0 };
  let state = applyEvent(seated(), frame("dealer_selection_started", {
    spread_size: 48, taken: [],
  }, selection));
  assert.equal(mustDraw(state), true);

  state = applyEvent(state, frame("draw_made", {
    player_id: "p-west", position: 3, card: "AS",
  }, selection));
  assert.equal(mustDraw(state), true, "another seat's draw is not mine");

  state = applyEvent(state, frame("draw_made", {
    player_id: "p-south", position: 7, card: "KH",
  }, selection));
  assert.equal(mustDraw(state), false);
  assert.deepEqual([...takenPositions(state)].sort((a, b) => a - b), [3, 7]);
});

test("nobody draws outside dealer selection", () => {
  assert.equal(mustDraw(seated()), false);
});

// ---------------------------------------------------------------------------
// Bidding (UI-10)
// ---------------------------------------------------------------------------

test("the minimum bid comes from the prompt, not from arithmetic here", () => {
  const bidding = { phase: "BIDDING", current_player_id: "p-south", paused: null, round_number: 1 };
  const state = applyEvent(
    seated(), frame("turn_prompt", { phase: "BIDDING", minimum_bid: 310, may_pass: true }, bidding),
  );
  assert.equal(minimumBid(state), 310);
  assert.equal(minimumBid(seated()), null);
});

test("nothing is playable while the table is paused (RT-9)", () => {
  // A pause is a state the game occupies: the server rejects a play made
  // during one as out-of-phase ("The completed trick has not been cleared
  // yet."), so the next leader must not be offered a card it cannot play.
  const paused = {
    phase: "PLAYING", current_player_id: "p-south", paused: "trick_clear", round_number: 1,
  };
  const state = [
    frame("turn_prompt", { phase: "PLAYING", legal_plays: ["AS", "KS"] }),
    frame("trick_completed", { winner_player_id: "p-west", cards: [] }, paused),
  ].reduce(applyEvent, seated());

  assert.equal(state.prompt.legalPlays.includes("AS"), true, "the prompt still stands");
  assert.equal(isLegalPlay(state, "AS"), false, "but the card is not offered");
});

test("a card becomes playable again once the pause ends", () => {
  const running = {
    phase: "PLAYING", current_player_id: "p-south", paused: null, round_number: 1,
  };
  const state = [
    frame("turn_prompt", { phase: "PLAYING", legal_plays: ["AS"] }),
    frame("trick_completed", { winner_player_id: "p-west", cards: [] }, {
      ...running, paused: "trick_clear",
    }),
    frame("trick_cleared", {
      winner_player_id: "p-west", next_leader_player_id: "p-south",
    }, running),
  ].reduce(applyEvent, seated());
  assert.equal(isLegalPlay(state, "AS"), true);
});

test("a fanned hand is centred, evenly stepped, and turns left to right", () => {
  const angles = fanAngles(12);
  assert.equal(angles.length, 12);
  assert.ok(angles[0] < 0 && angles[11] > 0, "the fan opens both ways from the middle");
  assert.ok(
    Math.abs(angles[0] + angles[11]) < 0.01,
    "the outermost cards lean equally far, in opposite directions",
  );

  // The angles are rounded to two places before they reach the style
  // attribute, so equal steps are equal to within that rounding.
  const steps = angles.slice(1).map((angle, index) => angle - angles[index]);
  for (const step of steps) {
    assert.ok(Math.abs(step - steps[0]) < 0.03, "every card turns by the same step");
  }
  assert.ok(steps[0] > 0, "the fan turns clockwise, so the cards spread rightwards");
});

test("a fan closes up as the hand is played out, rather than re-spreading it", () => {
  // A real hand narrows as cards leave it: the step stays put and the arc
  // shrinks, so the remaining cards do not drift apart.
  const twelve = fanAngles(12);
  const four = fanAngles(4);
  const step = (angles) => angles[1] - angles[0];
  assert.ok(Math.abs(step(twelve) - step(four)) < 0.03);
  assert.ok(four[3] - four[0] < twelve[11] - twelve[0]);
});

test("a fan of one card lies flat, and a fan of none is empty", () => {
  assert.deepEqual(fanAngles(1), [0]);
  assert.deepEqual(fanAngles(0), []);
});

test("play has begun once a leader is named, not once a card is played", () => {
  // What the pass display waits for: the auction winner being on turn to lead
  // is the moment the four cards received have been read and the table needs
  // the room (UI-12, FR-50a).
  const melded = applyEvent(seated(), frame("meld_exposed", {
    player_id: "p-south", units: [], total: 40,
  }));
  assert.equal(playHasBegun(melded), false);

  const leading = applyEvent(melded, frame("play_begun", { leader_player_id: "p-south" }));
  assert.equal(playHasBegun(leading), true, "before a card has been played");
});

// ---------------------------------------------------------------------------
// The scattered spread (FR-11c)
// ---------------------------------------------------------------------------

/** A repeatable stand-in for Math.random, so a scatter can be asserted on. */
function pseudoRandom(seed = 1) {
  let value = seed;
  return () => {
    value = (value * 1103515245 + 12345) % 2147483648;
    return value / 2147483648;
  };
}

test("every card of the spread lands inside the area it is thrown over", () => {
  const spots = scatter(48, pseudoRandom());
  assert.equal(spots.length, 48);
  for (const spot of spots) {
    // The fractions are of the room left once the card's own size is off the
    // area, so 0 and 1 are both still wholly inside it (table.css).
    assert.ok(spot.x >= 0 && spot.x <= 1, `x in the area: ${spot.x}`);
    assert.ok(spot.y >= 0 && spot.y <= 1, `y in the area: ${spot.y}`);
  }
});

test("the spread covers the whole area rather than clumping in it", () => {
  // What a grid buys over 48 uniform random points: no quarter of the area
  // left bare, and none of them holding half the deck.
  const spots = scatter(48, pseudoRandom(7));
  const quarters = [0, 0, 0, 0];
  for (const spot of spots) {
    quarters[(spot.x < 0.5 ? 0 : 1) + (spot.y < 0.5 ? 0 : 2)] += 1;
  }
  for (const count of quarters) {
    assert.ok(count >= 8, `every quarter of the table gets cards: ${quarters}`);
  }
});

test("the cards are turned every which way, and no two spots are alike", () => {
  const spots = scatter(48, pseudoRandom(3));
  assert.ok(spots.some((spot) => spot.tilt < -4), "some cards lean left");
  assert.ok(spots.some((spot) => spot.tilt > 4), "some cards lean right");
  const places = new Set(spots.map((spot) => `${spot.x},${spot.y}`));
  assert.equal(places.size, spots.length, "no two cards fall on the same spot");
});

test("the stacking order is a shuffle, not the order the cards were laid", () => {
  const spots = scatter(48, pseudoRandom(11));
  const order = spots.map((spot) => spot.z);
  assert.deepEqual([...order].sort((a, b) => a - b), [...Array(48).keys()]);
  assert.notDeepEqual(order, [...Array(48).keys()], "which card is on top is chance");
});

test("a spread thrown again lands differently", () => {
  // FR-14 reshuffles and deals the spread afresh; a deck that landed the
  // same way twice would not read as a new one.
  const first = scatter(48, pseudoRandom(1));
  const second = scatter(48, pseudoRandom(2));
  assert.notDeepEqual(first, second);
});

test("an empty spread is scattered emptily", () => {
  assert.deepEqual(scatter(0, pseudoRandom()), []);
});
