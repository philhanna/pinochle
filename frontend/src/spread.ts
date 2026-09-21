// The face-down spread the dealer is drawn from (FR-11, FR-11a, FR-11c).
//
// A deck thrown across the felt rather than dealt into ranks: the cards land
// irregularly and lie across one another, so the one a player reaches for may
// be under another. Dragging a card moves it aside; clicking one draws it.
// Telling those two gestures apart is the whole of the pointer handling here —
// a press that travels was meant to move the card, a press that stays put was
// meant to choose it.
//
// Where each card lies is decided once per spread and then kept. The table is
// redrawn from the state after every frame (RT-5), and a deck that rearranged
// itself under the player's hand each time somebody else drew would be
// unusable.

import { backUrl } from "./cards.js";
import { mustDraw, scatter, takenPositions, type ScatterSpot } from "./layout.js";
import type { GameState } from "./state.js";

/** What the spread does when a card is chosen. */
export interface SpreadCallbacks {
  onDraw: (position: number) => void;
}

/** Draw the scattered spread into `root`, or clear it (FR-11c). */
export function renderSpread(
  root: HTMLElement, state: GameState, callbacks: SpreadCallbacks,
): void {
  root.hidden = state.phase !== "DEALER_SELECTION";
  if (root.hidden) {
    root.replaceChildren();
    return;
  }

  const spots = currentScatter(state);
  const taken = takenPositions(state);
  const drawable = mustDraw(state);

  const cards: HTMLElement[] = [];
  for (let position = 0; position < state.spreadSize; position += 1) {
    // A drawn card is off the table: it is face up in front of the seat that
    // took it, which is renderSeats' business (FR-11d, FR-15).
    const spot = spots[position];
    if (taken.has(position) || spot === undefined) {
      continue;
    }
    cards.push(cardBack(position, spot, drawable, callbacks));
  }
  root.replaceChildren(...cards);
}

/** Where the cards of the spread now on the table fell. */
let scattered: ScatterSpot[] = [];

/** Which spread `scattered` was thrown for (state.ts's `spreadId`). */
let scatteredFor = -1;

/** What the player has done to each card they have moved. */
let moved = new Map<number, Moved>();

/**
 * Where a card has been pushed to, and how far up the pile it went.
 *
 * Both outlive the redraw that follows the drag, or a card dragged clear of
 * the one beneath it would jump back to where it was thrown the moment
 * anybody else drew.
 */
interface Moved {
  /** Its displacement from where it was thrown, in stage pixels. */
  x: number;
  y: number;
  /** Its place in the order cards were picked up in. */
  lift: number;
}

/**
 * The scatter for the spread now on the table, thrown once and then kept.
 *
 * A reshuffled spread (FR-14) is a new deck on the table, so it gets a new
 * scatter and forgets where the last one's cards had been pushed to.
 */
function currentScatter(state: GameState): ScatterSpot[] {
  if (state.spreadId !== scatteredFor || scattered.length !== state.spreadSize) {
    scattered = scatter(state.spreadSize);
    scatteredFor = state.spreadId;
    moved = new Map();
  }
  return scattered;
}

/** One face-down card, lying where it fell, with both gestures on it. */
function cardBack(
  position: number,
  spot: ScatterSpot,
  drawable: boolean,
  callbacks: SpreadCallbacks,
): HTMLElement {
  const element = document.createElement("img");
  element.className = "card";
  element.src = backUrl();
  element.alt = "";
  // The browser's own image drag would fight the pointer handling below,
  // which is what moves a card.
  element.draggable = false;

  element.style.setProperty("--x", String(spot.x));
  element.style.setProperty("--y", String(spot.y));
  element.style.setProperty("--tilt", `${spot.tilt}deg`);
  // A card the player has moved lies over every card they have not, in the
  // order they moved them; the rest lie as they were thrown.
  const shift = moved.get(position);
  element.style.zIndex = String(shift === undefined ? spot.z : LIFTED_Z + shift.lift);
  place(element, shift);

  if (drawable) {
    element.classList.add("drawable");
    element.addEventListener("click", () => {
      // The click the browser sends after a drag is not a choice of card.
      if (dragged) {
        dragged = false;
        return;
      }
      callbacks.onDraw(position);
    });
  }
  element.addEventListener("pointerdown", (event) => takeHold(event, element, position));
  return element;
}

/** Put a card where it has been pushed to, or where it was thrown. */
function place(element: HTMLElement, shift: Moved | undefined): void {
  element.style.setProperty("--dx", `${shift?.x ?? 0}px`);
  element.style.setProperty("--dy", `${shift?.y ?? 0}px`);
}

/** True while a card is under the pointer, so a redraw cannot pull it away. */
let moving = false;

/** True from the end of a drag until the click it produces is thrown away. */
let dragged = false;

/** How many cards have been picked up, so each lands over the last. */
let lifts = 0;

/**
 * Follow the pointer with this card, and settle which gesture it was.
 *
 * The threshold is what separates the two: until the pointer has travelled
 * far enough the card has not moved at all, so a hand that shifts a pixel or
 * two while clicking still draws the card it clicked.
 */
function takeHold(event: PointerEvent, element: HTMLElement, position: number): void {
  if (event.button !== 0) {
    return;
  }
  event.preventDefault();
  dragged = false;

  const scale = stageScale(element);
  const lift = lifts + 1;
  const from = moved.get(position) ?? { x: 0, y: 0, lift };
  const startX = event.clientX;
  const startY = event.clientY;
  let hasMoved = false;

  element.setPointerCapture(event.pointerId);

  const onMove = (move: PointerEvent): void => {
    // The stage is one fixed size scaled to the window (UI-17), so pointer
    // travel is in window pixels and the card is placed in stage ones.
    const dx = (move.clientX - startX) / scale;
    const dy = (move.clientY - startY) / scale;
    if (!hasMoved && Math.abs(dx) + Math.abs(dy) < DRAG_THRESHOLD_PX) {
      return;
    }
    if (!hasMoved) {
      // The card comes up over the rest as it starts to move, and stays over
      // them once it is put down: one dragged clear of the card beneath it
      // must not settle back under a third. A press that never became a drag
      // disturbs nothing.
      hasMoved = true;
      moving = true;
      lifts = lift;
      element.style.zIndex = String(LIFTED_Z + lift);
      element.classList.add("moving");
    }
    const shift = { x: from.x + dx, y: from.y + dy, lift };
    moved.set(position, shift);
    place(element, shift);
  };

  const letGo = (): void => {
    element.removeEventListener("pointermove", onMove);
    element.removeEventListener("pointerup", letGo);
    element.removeEventListener("pointercancel", letGo);
    element.classList.remove("moving");
    moving = false;
    dragged = hasMoved;
    if (hasMoved) {
      // Redraws were held off while the card was under the pointer; whatever
      // arrived meanwhile is drawn now that it is not. After the click this
      // drag is about to produce, so the card is still there to swallow it.
      window.setTimeout(() => document.dispatchEvent(new CustomEvent("redraw")), 0);
    }
  };

  element.addEventListener("pointermove", onMove);
  element.addEventListener("pointerup", letGo);
  element.addEventListener("pointercancel", letGo);
}

// Clear of every z-index the scatter itself hands out, which are the card
// positions and so are fewer than the deck is deep.
const LIFTED_Z = 1000;

// Far enough that a click is not a drag, short enough that a drag is not
// first a click.
const DRAG_THRESHOLD_PX = 4;

/** Whether a card is being dragged right now. */
export function isMovingCard(): boolean {
  return moving;
}

/** How far the stage is scaled to the window, so a card keeps up (UI-17). */
function stageScale(element: HTMLElement): number {
  const stage = element.closest<HTMLElement>("#stage");
  if (stage === null || stage.offsetWidth === 0) {
    return 1;
  }
  return stage.getBoundingClientRect().width / stage.offsetWidth;
}
