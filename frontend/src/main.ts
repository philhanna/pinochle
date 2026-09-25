// Entry point for a player's table.
//
// The shape of the whole client: frames in, state folded, table drawn. No
// timers, no polling, and no rule decided here — the server owns the game
// (ARC-2), owns every pause (RT-8), and says what this seat may do.

import { ApiError } from "./api.js";
import * as actions from "./actions.js";
import { DEAL_PACKET_COUNT, DEAL_PACKET_MS, dealingView } from "./deal.js";
import { clearSelection } from "./hand.js";
import { resetPanel } from "./panels.js";
import { openStream, playerStreamUrl, type ConnectionState } from "./stream.js";
import { applyEvent, initialState, type GameState } from "./state.js";
import {
  hideLastTrick, noteResort, renderTable, showConnection, showError, takenStackRect,
  type TableCallbacks,
} from "./table.js";
import { sweepTrick } from "./sweep.js";
import { resolveSeat } from "./token.js";
import type { Frame, Seat } from "./types.js";

let state: GameState = initialState();

/** Set once the seat is known; every redraw goes through it. */
let callbacks: TableCallbacks | null = null;

/**
 * Whether the stream is currently delivering.
 *
 * The client holds no game rules (ARC-2), but it does know whether it is
 * still being told what happens, and that is a fact about this browser that
 * no server event can carry.
 */
let connection: ConnectionState = "connecting";

/** The cosmetic deal currently being shown, if any. */
let dealPacketsShown: number | null = null;

/** The packet currently travelling from the dealer to a hand. */
let dealPacketInFlight: number | null = null;

/** Frames that arrived while the visible deal was catching up. */
const queuedFrames: Frame[] = [];

/** Whether a completed trick is being carried to its stack (UI-15). */
let trickSweeping = false;

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
    onFrame: receiveFrame,
    onError: (message) => showError(message),
    onConnection: (next) => {
      connection = next;
      showConnection(next);
    },
  });

  // The hand is not redrawn during a drag, so the drop or the abandonment of
  // one is where the deferred redraw happens.
  document.addEventListener("dragend", () => window.setTimeout(render, 0));
  // The last-trick button and the pass selection ask for a redraw without any
  // frame having arrived.
  document.addEventListener("redraw", () => render());
}

/** Apply a frame now, or preserve its order behind the visible deal. */
function receiveFrame(frame: Frame): void {
  if (dealPacketsShown !== null || trickSweeping) {
    queuedFrames.push(frame);
    return;
  }
  if (frame.type === "trick_cleared" && beginSweep(frame)) {
    return;
  }
  applyFrame(frame);
}

/** Fold a frame into the state and draw it. */
function applyFrame(frame: Frame): void {
  state = applyEvent(state, frame);
  afterFrame(frame);
  if (frame.type === "cards_dealt" && state.hand.length > 0) {
    beginVisibleDeal();
  } else {
    render();
  }
}

/**
 * Carry the trick to the winner's stack before the frame is folded in, so the
 * table still holds it while it flies. Frames that arrive meanwhile wait.
 */
function beginSweep(frame: Frame): boolean {
  const winner = frame.payload["winner_player_id"];
  const target = typeof winner === "string" ? takenStackRect(state, winner) : null;
  if (target === null) {
    return false;
  }
  const landed = () => {
    trickSweeping = false;
    // Not receiveFrame: that would sweep the same trick again, forever.
    applyFrame(frame);
    while (queuedFrames.length > 0 && !trickSweeping && dealPacketsShown === null) {
      const next = queuedFrames.shift();
      if (next !== undefined) {
        receiveFrame(next);
      }
    }
  };
  trickSweeping = true;
  if (sweepTrick(target, landed)) {
    return true;
  }
  trickSweeping = false;
  return false;
}

/** Reveal one clockwise packet at a human dealer's pace. */
function beginVisibleDeal(): void {
  dealPacketsShown = 0;
  dealPacketInFlight = 0;
  render();

  const nextPacket = () => {
    if (dealPacketsShown === null) {
      return;
    }
    dealPacketsShown += 1;
    if (dealPacketsShown < DEAL_PACKET_COUNT) {
      dealPacketInFlight = dealPacketsShown;
      render();
      window.setTimeout(nextPacket, DEAL_PACKET_MS);
      return;
    }

    dealPacketsShown = null;
    dealPacketInFlight = null;
    while (queuedFrames.length > 0 && dealPacketsShown === null) {
      const frame = queuedFrames.shift();
      if (frame !== undefined) {
        receiveFrame(frame);
      }
    }
    render();
  };

  window.setTimeout(nextPacket, DEAL_PACKET_MS);
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
  // Every action goes through here, so this is the one place that can stop a
  // seat acting into a connection that is not there. Sending anyway is worse
  // than not sending: the server would accept the move and carry the game on
  // without this player, whose screen would stay frozen on the turn they
  // thought they had just taken.
  const attempt = (work: () => Promise<void>) => {
    if (connection !== "live") {
      showError("Not connected — waiting for the stream to come back.");
      return;
    }
    work().catch((error: unknown) => {
      showError(error instanceof ApiError ? error.message : String(error));
    });
  };

  return {
    onDraw: (position) => attempt(() => actions.draw(seat, position)),
    onPlay: (card) => attempt(() => actions.play(seat, card)),
    onBid: (amount) => attempt(() => actions.bid(seat, amount)),
    onContract: (accept) => attempt(() => actions.decideContract(seat, accept)),
    onTrump: (suit) => attempt(() => actions.nameTrump(seat, suit)),
    onPass: (cards) => {
      clearSelection();
      attempt(() => actions.passCards(seat, cards));
    },
    onAcknowledge: (holdId) => attempt(() => actions.acknowledge(seat, holdId)),
    onBeginPlay: () => attempt(() => actions.beginPlay(seat)),
    onTossIn: () => attempt(() => actions.tossIn(seat)),
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
    const shown = dealPacketsShown === null ? state : dealingView(state, dealPacketsShown);
    renderTable(shown, callbacks, dealPacketInFlight);
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
