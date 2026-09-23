// The controls for whatever this seat is being asked to do.
//
// One panel at a time, driven by the turn prompt: bid, accept or decline,
// name trump, pass, meld, or nothing at all. The prompt is private to the
// seat whose turn it is, so a client never shows another seat's controls.

import { faceUrl, type CardCode, type SuitName } from "./cards.js";
import { SUITS, holdBeforePlay, minimumBid, passCount, suitGlyph } from "./layout.js";
import { dropIntoSelection, selectedCards, type HandCallbacks } from "./hand.js";
import type { GameState } from "./state.js";

/** What the panels do when a control is used. */
export interface PanelCallbacks extends HandCallbacks {
  onBid: (amount: number | null) => void;
  onContract: (accept: boolean) => void;
  onTrump: (suit: SuitName) => void;
  onPass: (cards: CardCode[]) => void;
  onBeginPlay: () => void;
  onTossIn: () => void;
  /**
   * Release the hold the table is stopped on (RT-13, UI-19a).
   *
   * A panel control needs this because the meld panel's Play button does
   * exactly what the notice area's Continue does, and the notice is where
   * that hold is otherwise released from.
   */
  onAcknowledge: (holdId: number) => void;
}

/**
 * What the panel currently shows, so an unrelated frame does not rebuild it.
 *
 * Without this, a half-typed bid would be replaced by the default every time
 * any frame arrived.
 */
let rendered: string | null = null;

/** Forget what is on screen, so the next render rebuilds the panel. */
export function resetPanel(): void {
  rendered = null;
}

/** Draw the controls for this seat's current turn, if it has one. */
export function renderPanel(
  root: HTMLElement, state: GameState, callbacks: PanelCallbacks,
): void {
  const signature = JSON.stringify([state.prompt, selectedCards(state), state.contract]);
  if (signature === rendered) {
    return;
  }
  rendered = signature;

  const phase = state.prompt?.phase;
  switch (phase) {
    case "BIDDING":
      root.replaceChildren(biddingPanel(state, callbacks));
      break;
    case "CONFIRMING":
      root.replaceChildren(confirmPanel(state, callbacks));
      break;
    case "TRUMP":
      root.replaceChildren(trumpPanel(callbacks));
      break;
    case "PASSING":
      root.replaceChildren(passPanel(state, callbacks));
      break;
    case "MELDING":
      root.replaceChildren(meldPanel(state, callbacks));
      break;
    default:
      root.replaceChildren();
  }
  root.hidden = root.childElementCount === 0;
}

/** Bid entry, constrained to multiples of ten at or above the minimum (UI-10). */
function biddingPanel(state: GameState, callbacks: PanelCallbacks): HTMLElement {
  const minimum = minimumBid(state) ?? 250;
  const panel = box("Your bid");

  const input = document.createElement("input");
  input.type = "number";
  input.min = String(minimum);
  input.step = "10";
  input.value = String(minimum);
  input.className = "bid-amount";

  const place = button(`Bid`, "primary", () => {
    const amount = Number(input.value);
    // The step and minimum are advice a browser gives; the check is here too,
    // and the server checks again regardless (ARC-2).
    if (!Number.isInteger(amount) || amount < minimum || amount % 10 !== 0) {
      input.classList.add("bad");
      return;
    }
    input.classList.remove("bad");
    callbacks.onBid(amount);
  });

  const raise = (by: number) => button(`+${by}`, "", () => {
    input.value = String(Number(input.value) + by);
  });

  panel.append(
    hint(`Minimum ${minimum}, in tens.`),
    row(input, raise(10), raise(50), place, button("Pass", "", () => callbacks.onBid(null))),
  );
  return panel;
}

/** A lone bidder's choice: be held to the bid, or throw the round in (FR-32). */
function confirmPanel(state: GameState, callbacks: PanelCallbacks): HTMLElement {
  const amount = state.prompt?.amount ?? state.offer?.amount ?? 0;
  const panel = box("You are the only bidder");
  panel.append(
    hint(`Take the contract at ${amount}, or decline and throw the round in.`),
    row(
      button(`Accept ${amount}`, "primary", () => callbacks.onContract(true)),
      button("Decline", "danger", () => callbacks.onContract(false)),
    ),
  );
  return panel;
}

/** The trump picker (UI-11). */
function trumpPanel(callbacks: PanelCallbacks): HTMLElement {
  const panel = box("Name trump");
  panel.append(row(...SUITS.map((suit) => {
    const { glyph, red } = suitGlyph(suit);
    const control = button(`${glyph} ${suit.slice(0, 1) + suit.slice(1).toLowerCase()}`, "suit", () => {
      callbacks.onTrump(suit);
    });
    control.classList.toggle("red", red);
    return control;
  })));
  return panel;
}

/**
 * The pass: choose exactly four and confirm (UI-12).
 *
 * The tray is a drop target as well as a readout, so dragging works here
 * exactly as it does over the table (UI-8).
 */
function passPanel(state: GameState, callbacks: PanelCallbacks): HTMLElement {
  const count = passCount(state);
  const chosen = selectedCards(state);
  const partner = state.seats.find(
    (seat) => seat.teamId === state.me?.teamId && seat.playerId !== state.me?.playerId,
  );

  const panel = box(`Pass ${count} cards to ${partner?.name ?? "your partner"}`);

  const tray = document.createElement("div");
  tray.className = "tray";
  tray.id = "pass-tray";
  tray.append(...chosen.map((card) => {
    const image = document.createElement("img");
    image.className = "card small";
    image.src = faceUrl(card);
    image.alt = card;
    return image;
  }));
  for (let i = chosen.length; i < count; i += 1) {
    const slot = document.createElement("div");
    slot.className = "card slot";
    tray.append(slot);
  }
  tray.addEventListener("dragover", (event) => event.preventDefault());
  tray.addEventListener("drop", (event) => {
    event.preventDefault();
    dropIntoSelection(event, state, callbacks);
  });

  const confirm = button(`Pass these ${count}`, "primary", () => callbacks.onPass(chosen));
  confirm.disabled = chosen.length !== count;

  panel.append(hint("Click a card, or drag it here."), tray, row(confirm));
  return panel;
}

/** The auction winner plays it out, or concedes, while the meld is reviewed. */
function meldPanel(state: GameState, callbacks: PanelCallbacks): HTMLElement {
  const panel = box("Your contract");
  const mine = state.teamMeld[state.me?.teamId ?? ""] ?? 0;
  const needed = (state.contract?.amount ?? 0) - mine;
  panel.append(
    hint(
      `Your side has ${mine} in meld; ${needed > 0 ? `${needed} more` : "nothing more"} `
      + `is needed in cards. Play it out, or toss it in and concede the contract.`,
    ),
    row(
      button("Play", "primary", () => beginPlay(state, callbacks)),
      button("Toss in", "danger", () => callbacks.onTossIn()),
    ),
  );
  return panel;
}

/**
 * Begin trick play, by whichever route is open (FR-50a, UI-19a).
 *
 * The meld is on the table behind a hold while it is read (RT-13), and the
 * server refuses `begin-play` until that hold is released — so releasing it
 * *is* how play begins, and this button does exactly what the Continue
 * control in the notice area does. The direct call is the fallback for a
 * table sitting in the melding phase with no hold in front of it, where
 * Continue would not be on screen either.
 */
function beginPlay(state: GameState, callbacks: PanelCallbacks): void {
  const hold = holdBeforePlay(state);
  if (hold === null) {
    callbacks.onBeginPlay();
    return;
  }
  callbacks.onAcknowledge(hold);
}

/** A titled panel. */
function box(title: string): HTMLElement {
  const panel = document.createElement("div");
  panel.className = "panel-box";
  const heading = document.createElement("h2");
  heading.textContent = title;
  panel.append(heading);
  return panel;
}

/** A row of controls. */
function row(...children: (HTMLElement | Text)[]): HTMLElement {
  const element = document.createElement("div");
  element.className = "panel-row";
  element.append(...children);
  return element;
}

/** A line of explanation under a panel title. */
function hint(text: string): HTMLElement {
  const element = document.createElement("p");
  element.className = "panel-hint";
  element.textContent = text;
  return element;
}

/** A button. */
function button(label: string, className: string, onClick: () => void): HTMLButtonElement {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  element.textContent = label;
  element.addEventListener("click", onClick);
  return element;
}
