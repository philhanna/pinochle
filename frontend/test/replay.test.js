// Replaying a real seat's stream (docs/impl.md B1's review point).
//
// The fixture is not hand-written: scripts/record_frames.py plays an
// all-computer game through the real service and records what one seat's
// stream carried, encoded by the real encoder. So it cannot drift from the
// wire format, and it has the awkward properties of a real stream — notably
// sequence numbers with gaps where other seats' private frames fell.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { applyEvent, initialState, seatOf } from "../dist/state.js";
import { isSuit } from "../dist/cards.js";
import { isLegalPlay, placement, trickCards } from "../dist/layout.js";
import { meldLines, scoreboard, statusLine, summaryRows } from "../dist/view.js";

const frames = JSON.parse(
  readFileSync(new URL("./fixtures/seat-stream.json", import.meta.url), "utf8"),
);

/** Fold every frame in, calling `check(state, frame)` after each one. */
function replayAll(check = () => {}) {
  let state = initialState();
  for (const frame of frames) {
    state = applyEvent(state, frame);
    check(state, frame);
  }
  return state;
}

test("the fixture is a real seat's stream, gaps and all", () => {
  const seqs = frames.map((f) => f.seq);
  assert.ok(frames.length > 100, "a round's worth of frames");
  assert.ok(seqs.every((s, i) => i === 0 || s > seqs[i - 1]), "monotonic");
  assert.ok(
    seqs[seqs.length - 1] - seqs[0] + 1 > seqs.length,
    "with gaps, where other seats' private frames fell",
  );
});

test("the whole stream replays without error", () => {
  const state = replayAll();
  assert.equal(state.me.playerId, "p-south");
  assert.equal(state.me.seat, "SOUTH");
  assert.equal(state.me.teamId, "NS");
  assert.equal(state.seats.length, 4);
  assert.equal(state.lastSeq, frames[frames.length - 1].seq);
});

test("this hand's size always matches this seat's own count", () => {
  // The strongest single invariant available: the hand is tracked card by
  // card from private frames, the count from public ones, and they are
  // maintained by different branches of the reducer. They may not diverge.
  replayAll((state) => {
    if (state.me === null || Object.keys(state.handCounts).length === 0) {
      return;
    }
    assert.equal(
      state.hand.length,
      state.handCounts[state.me.playerId],
      `hand and count diverged at seq ${state.lastSeq}`,
    );
  });
});

test("no count ever goes negative and no hand exceeds its maximum", () => {
  replayAll((state) => {
    for (const [playerId, count] of Object.entries(state.handCounts)) {
      assert.ok(count >= 0, `${playerId} went negative at seq ${state.lastSeq}`);
      assert.ok(count <= 16, `${playerId} held ${count} at seq ${state.lastSeq}`);
    }
  });
});

test("every seat holds twelve cards when play begins", () => {
  // The pass is complete and no trick has been played, so the deal is back to
  // even. This is what catches a count adjusted at one end of the pass but
  // not the other — an error the seat's own hand would never reveal.
  let checked = 0;
  replayAll((state, frame) => {
    if (frame.type !== "play_begun") {
      return;
    }
    checked += 1;
    for (const [playerId, count] of Object.entries(state.handCounts)) {
      assert.equal(count, 12, `${playerId} held ${count} as play began`);
    }
  });
  assert.ok(checked > 0, "the recording should reach trick play");
});

test("the trick never holds more than four cards", () => {
  replayAll((state) => {
    assert.ok(state.trick.length <= 4, `trick of ${state.trick.length}`);
  });
});

test("no card-point total exists until the round is scored (UI-14c)", () => {
  // Counting the cards as they fall is part of playing well, so the client
  // must not be able to show a running total even by accident. Before the
  // round summary arrives, no card-point figure is anywhere in the state.
  replayAll((state) => {
    if (state.roundSummary === null) {
      assert.ok(
        !JSON.stringify(state).includes("cardPoints"),
        `a card-point total appeared mid-round, at seq ${state.lastSeq}`,
      );
    }
  });
});

test("trump moves to the left of the hand when it is named (FR-23a)", () => {
  let seen = false;
  replayAll((state) => {
    if (state.trump === null || state.hand.length === 0) {
      return;
    }
    const trumpCards = state.hand.filter((card) => isSuit(card, state.trump));
    if (trumpCards.length === 0) {
      return;
    }
    seen = true;
    assert.deepEqual(
      state.hand.slice(0, trumpCards.length),
      trumpCards,
      "trump should be the leftmost group",
    );
  });
  assert.ok(seen, "the recorded game should reach a named trump with trump in hand");
});

test("the round summary's totals are the server's own (FR-66)", () => {
  const state = replayAll();
  const scored = frames.filter((f) => f.type === "round_scored");
  assert.ok(scored.length >= 1, "the recording covers a scored round");

  const last = scored[scored.length - 1].payload;
  for (const team of last.teams) {
    const held = state.teams.find((t) => t.teamId === team.team_id);
    // The next round may already have started, which clears the summary but
    // must never clear a cumulative score.
    assert.equal(held.score, team.cumulative_score);
  }
});

test("every seat that melded is one of the four at the table", () => {
  const state = replayAll((s) => {
    for (const playerId of Object.keys(s.meld)) {
      assert.notEqual(seatOf(s, playerId), null, `${playerId} is not seated`);
    }
  });
  assert.ok(state.seats.length === 4);
});

test("every derivation survives a whole recorded game", () => {
  // The rendering layer cannot be exercised without a DOM, but everything it
  // reads from can be: if a derivation throws or contradicts itself on real
  // frames, it does so here rather than on the table.
  let sawTrick = false;
  let sawStatus = false;
  replayAll((state) => {
    const spots = placement(state);
    // A client knows its own seat from the stream's first frame but learns the
    // table only from game_configured, so there is a window with neither.
    if (state.me !== null && state.seats.length === 4) {
      assert.equal(spots.bottom?.playerId, state.me.playerId, "the viewer sits at the bottom");
      assert.equal(spots.top?.teamId, state.me.teamId, "the partner sits across");
    }

    const cards = trickCards(state);
    assert.equal(cards.length, state.trick.length, "every played card has a seat");
    sawTrick ||= cards.length > 0;

    for (const card of state.hand) {
      // Legality is the server's answer; asking is never an error.
      assert.equal(typeof isLegalPlay(state, card), "boolean");
    }

    const line = statusLine(state);
    assert.equal(typeof line, "string");
    sawStatus ||= line !== "";

    const board = scoreboard(state);
    assert.ok(board.length >= 2 || state.teams.length === 0);
    if (state.roundSummary === null) {
      assert.ok(
        !JSON.stringify(board).toLowerCase().includes("point"),
        `the scoreboard showed points mid-round at seq ${state.lastSeq}`,
      );
    }
    summaryRows(state);
    meldLines(state);
  });
  assert.ok(sawTrick, "the recording should include cards on the table");
  assert.ok(sawStatus, "the recording should produce a status line");
});
