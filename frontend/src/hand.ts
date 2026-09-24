// This seat's own hand: drawing it, and getting a card out of it.
//
// UI-8 gives two gestures that must be exactly equivalent — drag a card to the
// table, or click it — so both end at the same call. UI-9 has the client mark
// which cards are legal and refuse to submit one that is not; the answer comes
// from the server's turn prompt, never from rules re-derived here (ARC-2).

import { backUrl, faceUrl, type CardCode } from "./cards.js";
import { fanAngles, isLegalPlay, passCount } from "./layout.js";
import type { GameState } from "./state.js";

/** What the hand does when a card is chosen. */
export interface HandCallbacks {
  onPlay: (card: CardCode) => void;
  onSelectionChange: (cards: CardCode[]) => void;
}

/**
 * Which cards are picked out for the pass, by position in the hand.
 *
 * By position and not by code: a hand can hold both copies of a card, and
 * choosing "the ten of spades" has to mean one of them.
 */
let selected = new Set<number>();

/** True while a drag is in flight, so a redraw cannot pull the card away. */
let dragging = false;

/** Forget any selection — called when the phase that needed one is over. */
export function clearSelection(): void {
  selected = new Set();
}

/** Whether a card is being dragged right now. */
export function isDragging(): boolean {
  return dragging;
}

/**
 * Mark the hand as just re-sorted, so the change is visible (FR-23a).
 *
 * Naming trump moves the trump suit to the left, and it is the only re-sort a
 * hand undergoes in a round. The cards are rebuilt rather than moved, so a CSS
 * transition has nothing to interpolate; a short pulse on the hand is what
 * keeps the cards from appearing to teleport.
 */
export function markResorted(root: HTMLElement): void {
  root.classList.remove("resorted");
  // Reading a layout property restarts the animation rather than letting the
  // class removal and re-addition collapse into no change at all.
  void root.offsetWidth;
  root.classList.add("resorted");
  window.setTimeout(() => root.classList.remove("resorted"), 900);
}

/**
 * Draw this seat's hand into `root` (UI-4).
 *
 * A card picked out for the pass leaves the hand for the tray, and the fan
 * closes up behind it: a card left standing in the hand, only marked, read
 * as a card still being held. The hand is also where a card dragged back out
 * of the tray is dropped.
 */
export function renderHand(root: HTMLElement, state: GameState, callbacks: HandCallbacks): void {
  const passing = passCount(state) > 0;
  if (!passing && selected.size > 0) {
    clearSelection();
  }

  const held = state.hand.flatMap((card, index) => (
    passing && selected.has(index) ? [] : [{ card, index }]
  ));
  const angles = fanAngles(held.length);
  root.replaceChildren(...held.map(({ card, index }, position) => (
    cardElement(card, index, position, angles[position] ?? 0, state, passing, callbacks)
  )));
  root.classList.toggle("choosing", passing);

  // Assigned rather than added, so a hand drawn many times holds one of each.
  root.ondragover = (event) => {
    if (passing) {
      event.preventDefault();
    }
  };
  root.ondrop = (event) => {
    event.preventDefault();
    const index = trayIndex(event);
    if (passing && index !== null) {
      returnToHand(index, state, callbacks);
    }
  };
}

/** One card in the hand, tilted into the fan, with both gestures wired to it. */
function cardElement(
  card: CardCode,
  index: number,
  position: number,
  angle: number,
  state: GameState,
  passing: boolean,
  callbacks: HandCallbacks,
): HTMLElement {
  const playable = isLegalPlay(state, card);
  const element = document.createElement("img");
  element.className = "card";
  element.src = faceUrl(card);
  element.alt = card;
  element.draggable = playable || passing;

  // The tilt is what places the card (see fanAngles); the stacking order is
  // what leaves its corner index showing, each card over the one to its left.
  //
  // The order goes into a custom property rather than into z-index itself, so
  // that the stacking stays in the stylesheet with the rest of the fan's
  // look: an inline z-index would outrank anything table.css had to say about
  // it. Nothing does change it now — a card pointed at keeps its place in
  // the hand and is marked in colour alone — and that is a rule worth keeping
  // where it can be seen.
  element.style.setProperty("--angle", `${angle}deg`);
  element.style.setProperty("--stack", String(position));

  // UI-9: legality is shown at all times during play, not only on hover, and
  // an illegal card is not merely unstyled — it cannot be submitted.
  if (state.prompt?.phase === "PLAYING") {
    element.classList.toggle("legal", playable);
    element.classList.toggle("illegal", !playable);
  }
  element.addEventListener("click", () => {
    if (passing) {
      toggle(index, state, callbacks);
    } else if (playable) {
      callbacks.onPlay(card);
    }
  });

  element.addEventListener("dragstart", (event) => {
    dragging = true;
    event.dataTransfer?.setData("text/plain", String(index));
    element.classList.add("lifted");
  });
  element.addEventListener("dragend", () => {
    dragging = false;
    element.classList.remove("lifted");
  });

  return element;
}

/** Add or remove a card from the pass selection, never exceeding the count. */
function toggle(index: number, state: GameState, callbacks: HandCallbacks): void {
  if (selected.has(index)) {
    selected.delete(index);
  } else if (selected.size < passCount(state)) {
    selected.add(index);
  } else {
    return;
  }
  callbacks.onSelectionChange(selectedCards(state));
}

/** The cards currently picked out, in hand order. */
export function selectedCards(state: GameState): CardCode[] {
  return chosenCards(state).map(({ card }) => card);
}

/**
 * The cards currently picked out with their places in the hand, in hand order.
 *
 * The tray needs the place as well as the card, to say which of two twins it
 * is handing back.
 */
export function chosenCards(state: GameState): { card: CardCode; index: number }[] {
  return [...selected]
    .sort((a, b) => a - b)
    .flatMap((index) => {
      const card = state.hand[index];
      return card === undefined ? [] : [{ card, index }];
    });
}

/** Put a card picked out for the pass back into the hand. */
export function returnToHand(index: number, state: GameState, callbacks: HandCallbacks): void {
  if (selected.delete(index)) {
    callbacks.onSelectionChange(selectedCards(state));
  }
}

/**
 * The drag data a card in the pass tray carries: its place in the hand, marked
 * so that it cannot be mistaken for a card dragged out of the hand itself.
 */
export function trayDragData(index: number): string {
  return `${TRAY_PREFIX}${index}`;
}

const TRAY_PREFIX = "tray:";

/** The hand position a drag out of the tray carried, or null for any other. */
function trayIndex(event: DragEvent): number | null {
  const raw = event.dataTransfer?.getData("text/plain") ?? "";
  if (!raw.startsWith(TRAY_PREFIX)) {
    return null;
  }
  const index = Number(raw.slice(TRAY_PREFIX.length));
  return Number.isInteger(index) ? index : null;
}

/**
 * Accept a card dropped somewhere, by the index the drag carried.
 *
 * Returns the card, or null if the drop carried nothing usable — a drag from
 * outside the page, say.
 */
export function droppedCard(event: DragEvent, state: GameState): CardCode | null {
  const raw = event.dataTransfer?.getData("text/plain");
  if (raw === undefined || raw === "") {
    return null;
  }
  const index = Number(raw);
  return Number.isInteger(index) ? state.hand[index] ?? null : null;
}

/** Select the dropped card for the pass, if it is not already chosen. */
export function dropIntoSelection(
  event: DragEvent, state: GameState, callbacks: HandCallbacks,
): void {
  const raw = event.dataTransfer?.getData("text/plain");
  const index = Number(raw);
  if (!Number.isInteger(index) || selected.has(index)) {
    return;
  }
  if (selected.size < passCount(state)) {
    selected.add(index);
    callbacks.onSelectionChange(selectedCards(state));
  }
}

/** A fan of face-down cards, for a hand this client may not see (UI-5). */
export function backsFan(count: number, vertical = false): HTMLElement {
  const fan = document.createElement("div");
  fan.className = vertical ? "fan vertical" : "fan";
  for (let i = 0; i < count; i += 1) {
    const back = document.createElement("img");
    back.className = "card back";
    back.src = backUrl();
    back.alt = "";
    fan.append(back);
  }
  return fan;
}
