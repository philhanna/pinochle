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

/** Draw this seat's hand into `root` (UI-4). */
export function renderHand(root: HTMLElement, state: GameState, callbacks: HandCallbacks): void {
  const passing = passCount(state) > 0;
  if (!passing && selected.size > 0) {
    clearSelection();
  }

  const angles = fanAngles(state.hand.length);
  root.replaceChildren(...state.hand.map((card, index) => (
    cardElement(card, index, angles[index] ?? 0, state, passing, callbacks)
  )));
  root.classList.toggle("choosing", passing);
}

/** One card in the hand, tilted into the fan, with both gestures wired to it. */
function cardElement(
  card: CardCode,
  index: number,
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
  // The order goes into a custom property rather than into z-index itself,
  // because an inline z-index outranks every rule in the stylesheet: it was
  // silently beating the one that brings the card under the pointer forward,
  // and the one that brings a card chosen for the pass clear of the cards
  // lying over it. table.css reads --stack, so those two can win.
  element.style.setProperty("--angle", `${angle}deg`);
  element.style.setProperty("--stack", String(index));

  // UI-9: legality is shown at all times during play, not only on hover, and
  // an illegal card is not merely unstyled — it cannot be submitted.
  if (state.prompt?.phase === "PLAYING") {
    element.classList.toggle("legal", playable);
    element.classList.toggle("illegal", !playable);
  }
  if (passing && selected.has(index)) {
    element.classList.add("chosen");
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
  return [...selected]
    .sort((a, b) => a - b)
    .flatMap((index) => {
      const card = state.hand[index];
      return card === undefined ? [] : [card];
    });
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
