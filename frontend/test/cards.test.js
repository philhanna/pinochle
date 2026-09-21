// Card ordering (FR-18, FR-23, FR-23a).
import { test } from "node:test";
import assert from "node:assert/strict";

import { removeOne, sortHand } from "../dist/cards.js";

test("sortHand groups by suit in spades, hearts, clubs, diamonds order", () => {
  const sorted = sortHand(["9C", "AD", "KH", "QS"]);
  assert.deepEqual(sorted, ["QS", "KH", "9C", "AD"]);
});

test("sortHand orders a suit descending, with the ten above the king", () => {
  // FR-18's pinochle-specific placement: 9 < J < Q < K < 10 < A.
  const sorted = sortHand(["9S", "JS", "QS", "KS", "TS", "AS"]);
  assert.deepEqual(sorted, ["AS", "TS", "KS", "QS", "JS", "9S"]);
});

test("sortHand moves trump to the left", () => {
  // FR-23a: diamonds first, then spades, hearts, clubs — still alternating.
  const sorted = sortHand(["9C", "AD", "KH", "QS"], "DIAMONDS");
  assert.deepEqual(sorted, ["AD", "QS", "KH", "9C"]);
});

test("the suits alternate in colour, whatever trump is (FR-23, FR-23a)", () => {
  const hand = ["9C", "AD", "KH", "QS"];
  const isRed = (card) => "HD".includes(card[1]);
  for (const trump of [null, "SPADES", "HEARTS", "CLUBS", "DIAMONDS"]) {
    const colours = sortHand(hand, trump).map(isRed);
    assert.deepEqual(
      colours, [colours[0], !colours[0], colours[0], !colours[0]],
      `suits do not alternate with trump ${trump}`,
    );
  }
});

test("a named trump leads its own hand (FR-23a)", () => {
  const hand = ["9C", "AD", "KH", "QS"];
  for (const [trump, first] of [
    ["SPADES", "S"], ["HEARTS", "H"], ["CLUBS", "C"], ["DIAMONDS", "D"],
  ]) {
    assert.equal(sortHand(hand, trump)[0][1], first);
  }
});

test("sortHand keeps both copies of a duplicated card", () => {
  const sorted = sortHand(["TS", "TS", "AS"]);
  assert.deepEqual(sorted, ["AS", "TS", "TS"]);
});

test("sortHand does not mutate its argument", () => {
  const hand = ["9C", "AS"];
  sortHand(hand);
  assert.deepEqual(hand, ["9C", "AS"]);
});

test("removeOne removes a single copy, not every match", () => {
  assert.deepEqual(removeOne(["TS", "TS", "AS"], "TS"), ["TS", "AS"]);
});

test("removeOne leaves a hand alone when the card is not in it", () => {
  assert.deepEqual(removeOne(["AS"], "9C"), ["AS"]);
});
