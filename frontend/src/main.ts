// Entry point for a player's table.
//
// The shape of the whole client: frames in, state folded, table drawn. No
// timers, no polling, and no rule decided here — the server owns the game
// (ARC-2), owns every pause (RT-8), and says what this seat may do.

import { ApiError } from "./api.js";
import * as actions from "./actions.js";
import { clearSelection } from "./hand.js";
import { resetPanel } from "./panels.js";
import { openStream, playerStreamUrl } from "./stream.js";
import { applyEvent, initialState, type GameState } from "./state.js";
import {
  hideLastTrick, noteResort, renderTable, showError, type TableCallbacks,
} from "./table.js";
import { resolveSeat } from "./token.js";
import type { Frame, Seat } from "./types.js";

let state: GameState = initialState();

/** Set once the seat is known; every redraw goes through it. */
let callbacks: TableCallbacks | null = null;

main();

/** Connect this seat's stream and draw the table from it. */
function main(): void {
  const seat = resolveSeat();
  if (seat === null) {
    showNoSeat();
    return;
  }

  fitStage();
  window.addEventListener("resize", fitStage);

  callbacks = buildCallbacks(seat);
  render();

  openStream(playerStreamUrl(seat), {
    onFrame: (frame) => {
      state = applyEvent(state, frame);
      afterFrame(frame);
      render();
    },
    onError: (message) => showError(message),
  });

  // The hand is not redrawn during a drag, so the drop or the abandonment of
  // one is where the deferred redraw happens.
  document.addEventListener("dragend", () => window.setTimeout(render, 0));
  // The last-trick button and the pass selection ask for a redraw without any
  // frame having arrived.
  document.addEventListener("redraw", () => render());
}

/**
 * Scale the fixed-size table to the window (UI-17).
 *
 * The layout is one fixed size and is scaled to fit rather than reflowed,
 * which is what lets four windows tiled on a single monitor each show a whole
 * table. Done here because CSS cannot divide a length by a length, so the
 * unitless ratio `scale()` needs cannot be expressed in the stylesheet.
 */
function fitStage(): void {
  const stage = document.getElementById("stage");
  if (stage === null) {
    return;
  }
  const scale = Math.min(
    window.innerWidth / stage.offsetWidth,
    window.innerHeight / stage.offsetHeight,
  );
  stage.style.setProperty("--stage-scale", String(scale));
}

/** Turn the table's requests into HTTP, and refusals into a visible message. */
function buildCallbacks(seat: Seat): TableCallbacks {
  const attempt = (work: Promise<void>) => {
    work.catch((error: unknown) => {
      showError(error instanceof ApiError ? error.message : String(error));
    });
  };

  return {
    onDraw: (position) => attempt(actions.draw(seat, position)),
    onPlay: (card) => attempt(actions.play(seat, card)),
    onBid: (amount) => attempt(actions.bid(seat, amount)),
    onContract: (accept) => attempt(actions.decideContract(seat, accept)),
    onTrump: (suit) => attempt(actions.nameTrump(seat, suit)),
    onPass: (cards) => {
      clearSelection();
      attempt(actions.passCards(seat, cards));
    },
    onBeginPlay: () => attempt(actions.beginPlay(seat)),
    onTossIn: () => attempt(actions.tossIn(seat)),
    onSelectionChange: () => render(),
  };
}

/** React to a frame beyond folding it into the state. */
function afterFrame(frame: Frame): void {
  if (frame.type === "trick_cleared") {
    // UI-14b allows the last trick to be reviewed during the following trick.
    // Closing the panel here keeps a player from staring at what silently
    // became a different trick.
    hideLastTrick();
  }
  if (frame.type === "round_started" || frame.type === "cards_passed") {
    clearSelection();
    resetPanel();
  }
  if (frame.type === "trump_named") {
    // FR-23a: trump moves to the left of the hand, and that re-sort must be
    // visible rather than instantaneous.
    noteResort();
  }
}

/** Draw the table from the current state. */
function render(): void {
  if (callbacks !== null) {
    renderTable(state, callbacks);
  }
}

/** Explain how to get a seat, for a page opened without a join link. */
function showNoSeat(): void {
  const stage = document.getElementById("stage");
  if (stage === null) {
    return;
  }
  const message = document.createElement("p");
  message.className = "no-seat";
  message.textContent =
    "No seat. Open a join link from the console at /admin — each seat has its "
    + "own link, and each one belongs in its own tab.";
  stage.replaceChildren(message);
}
