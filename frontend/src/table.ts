// Drawing the table.
//
// One function renders the whole thing from the state, because the state is
// the only model there is (RT-5) and a redraw is cheap at this size. The
// exception is the hand during a drag, which must not be pulled out from under
// the pointer.

import { backUrl, faceUrl } from "./cards.js";
import { backsFan, droppedCard, isDragging, renderHand } from "./hand.js";
import {
  isPaused, mustDraw, placement, takenPositions, trickCards,
} from "./layout.js";
import { renderPanel, type PanelCallbacks } from "./panels.js";
import type { GameState } from "./state.js";
import {
  bidHistory, gameOverText, meldLines, scoreboard, seatLabel, statusLine,
  summaryHeadline, summaryRows,
} from "./view.js";

/** Everything the table can ask of the player. */
export interface TableCallbacks extends PanelCallbacks {
  onDraw: (position: number) => void;
}

/** Whether the last completed trick is being shown (UI-14b). */
let showingLastTrick = false;

/** Draw the whole table. */
export function renderTable(state: GameState, callbacks: TableCallbacks): void {
  renderSeats(state);
  renderCentre(state, callbacks);
  renderScoreboard(state);
  renderStatus(state);
  renderPanelInto(state, callbacks);

  const hand = byId("hand");
  // A redraw mid-drag would destroy the element being dragged, so the hand
  // waits; dragend triggers the next redraw.
  if (hand !== null && !isDragging()) {
    renderHand(hand, state, callbacks);
  }
}

/** The three other seats, plus this one's own label (UI-1, UI-3, UI-5, UI-7). */
function renderSeats(state: GameState): void {
  const spots = placement(state);
  for (const spot of ["bottom", "left", "top", "right"] as const) {
    const element = byId(`seat-${spot}`);
    if (element === null) {
      continue;
    }
    const seat = spots[spot];
    if (seat === null) {
      element.replaceChildren();
      element.className = `seat ${spot}`;
      continue;
    }

    const label = document.createElement("div");
    label.className = "seat-name";
    label.textContent = seatLabel(state, seat);

    const children: HTMLElement[] = [label];
    if (spot !== "bottom") {
      const count = state.handCounts[seat.playerId] ?? 0;
      children.push(backsFan(count, spot === "left" || spot === "right"));
    }

    element.replaceChildren(...children);
    // The partnership is a class rather than a colour chosen here, so UI-3's
    // "visually distinguishable" is settled in the stylesheet.
    element.className = [
      "seat", spot, `team-${seat.teamId.toLowerCase()}`,
      seat.playerId === state.currentPlayerId ? "acting" : "",
      seat.playerId === state.thinkingPlayerId ? "thinking" : "",
      seat.type === "computer" ? "computer" : "human",
    ].filter(Boolean).join(" ");
  }
}

/** The middle of the table: the spread, the trick, the meld, or a summary. */
function renderCentre(state: GameState, callbacks: TableCallbacks): void {
  const centre = byId("centre");
  if (centre === null) {
    return;
  }

  if (state.gameOver !== null) {
    centre.replaceChildren(gameOverPanel(state));
    return;
  }
  if (state.roundSummary !== null) {
    centre.replaceChildren(summaryPanel(state));
    return;
  }
  if (state.phase === "DEALER_SELECTION") {
    centre.replaceChildren(spread(state, callbacks));
    return;
  }
  if (showingLastTrick && state.lastTrick !== null) {
    // The trick in progress stays underneath: UI-14b allows the last trick to
    // be reviewed *during* the following one, so reviewing must not stop play.
    centre.replaceChildren(lastTrickPanel(state), trickLayer(state, callbacks));
    return;
  }
  if (state.prompt?.phase === "MELDING" || Object.keys(state.meld).length > 0) {
    centre.replaceChildren(meldPanel(state), trickLayer(state, callbacks));
    return;
  }
  centre.replaceChildren(trickLayer(state, callbacks));
}

/**
 * The trick: each card nearer the seat that played it (UI-6).
 *
 * Also the drop target for a dragged card, which is the primary way to play
 * one (UI-8).
 */
function trickLayer(state: GameState, callbacks: TableCallbacks): HTMLElement {
  const layer = document.createElement("div");
  layer.className = "trick";
  layer.classList.toggle("paused", isPaused(state));

  for (const played of trickCards(state)) {
    const image = document.createElement("img");
    image.className = `card played ${played.spot}`;
    image.src = faceUrl(played.card);
    image.alt = played.card;
    if (played.playerId === state.trickWinnerPlayerId) {
      image.classList.add("winning");
    }
    layer.append(image);
  }

  layer.addEventListener("dragover", (event) => event.preventDefault());
  layer.addEventListener("drop", (event) => {
    event.preventDefault();
    const card = droppedCard(event, state);
    if (card !== null) {
      callbacks.onPlay(card);
    }
  });
  return layer;
}

/** The face-down spread every seat draws from (FR-11, FR-11a). */
function spread(state: GameState, callbacks: TableCallbacks): HTMLElement {
  const taken = takenPositions(state);
  const drawable = mustDraw(state);

  const element = document.createElement("div");
  element.className = "spread";

  for (let position = 0; position < state.spreadSize; position += 1) {
    const drawn = state.draws.find((draw) => draw.position === position);
    if (drawn !== undefined) {
      const face = document.createElement("img");
      face.className = "card small turned";
      face.src = faceUrl(drawn.card);
      face.alt = drawn.card;
      face.title = nameFor(state, drawn.playerId);
      element.append(face);
      continue;
    }

    const back = document.createElement("img");
    back.className = "card small";
    back.src = backUrl();
    back.alt = "";
    if (drawable && !taken.has(position)) {
      back.classList.add("drawable");
      back.addEventListener("click", () => callbacks.onDraw(position));
    }
    element.append(back);
  }
  return element;
}

/** Exposed meld, per seat and per team (UI-13). */
function meldPanel(state: GameState): HTMLElement {
  const panel = document.createElement("div");
  panel.className = "meld";

  for (const line of meldLines(state)) {
    const row = document.createElement("div");
    row.className = "meld-row";
    const who = document.createElement("span");
    who.className = "meld-who";
    who.textContent = line.name;
    const units = document.createElement("span");
    units.className = "meld-units";
    units.textContent = line.units.length === 0 ? "no meld" : line.units.join(", ");
    const total = document.createElement("span");
    total.className = "meld-total";
    total.textContent = String(line.total);
    row.append(who, units, total);
    panel.append(row);
  }

  for (const [teamId, total] of Object.entries(state.teamMeld)) {
    const row = document.createElement("div");
    row.className = "meld-row team";
    const name = state.teams.find((team) => team.teamId === teamId)?.name ?? teamId;
    row.append(text("meld-who", name), text("meld-units", "team meld"), text("meld-total", String(total)));
    panel.append(row);
  }
  return panel;
}

/** The last completed trick, on demand (UI-14b). */
function lastTrickPanel(state: GameState): HTMLElement {
  const panel = document.createElement("div");
  panel.className = "last-trick";
  const heading = document.createElement("h2");
  heading.textContent = "The last trick";
  panel.append(heading);

  const cards = document.createElement("div");
  cards.className = "tray";
  for (const played of trickCards(state, state.lastTrick?.plays ?? [])) {
    const wrapper = document.createElement("div");
    wrapper.className = "last-trick-card";
    const image = document.createElement("img");
    image.className = "card small";
    image.src = faceUrl(played.card);
    image.alt = played.card;
    if (played.playerId === state.lastTrick?.winnerPlayerId) {
      wrapper.classList.add("winning");
    }
    wrapper.append(image, text("who", nameFor(state, played.playerId)));
    cards.append(wrapper);
  }
  panel.append(cards);
  return panel;
}

/** The round summary (FR-66). */
function summaryPanel(state: GameState): HTMLElement {
  const panel = document.createElement("div");
  panel.className = "summary";

  const heading = document.createElement("h2");
  heading.textContent = summaryHeadline(state);
  panel.append(heading);

  const table = document.createElement("table");
  table.innerHTML =
    "<thead><tr><th>Team</th><th>Meld</th><th>Cards</th><th>Last</th>"
    + "<th>Round</th><th>Applied</th><th>Score</th></tr></thead>";
  const body = document.createElement("tbody");
  for (const row of summaryRows(state)) {
    const tr = document.createElement("tr");
    if (row.bid) {
      tr.className = "bid-team";
    }
    for (const value of [
      row.name, row.meld, row.cardPoints, row.lastTrickBonus,
      row.roundTotal, row.pointsApplied, row.cumulativeScore,
    ]) {
      const td = document.createElement("td");
      td.textContent = String(value);
      tr.append(td);
    }
    body.append(tr);
  }
  table.append(body);
  panel.append(table);
  return panel;
}

/** The final result (FR-71). */
function gameOverPanel(state: GameState): HTMLElement {
  const panel = document.createElement("div");
  panel.className = "summary over";
  const heading = document.createElement("h2");
  heading.textContent = "Game over";
  const line = document.createElement("p");
  line.textContent = gameOverText(state);
  panel.append(heading, line);
  return panel;
}

/** The persistent scoreboard and bid history (UI-14, UI-14a). */
function renderScoreboard(state: GameState): void {
  const element = byId("scoreboard");
  if (element === null) {
    return;
  }
  const children: HTMLElement[] = [];
  for (const line of scoreboard(state)) {
    const row = document.createElement("div");
    row.className = "score-row";
    row.append(text("score-label", line.label), text("score-value", line.value));
    children.push(row);
  }

  const bids = bidHistory(state);
  if (bids.length > 0) {
    const heading = document.createElement("div");
    heading.className = "score-heading";
    heading.textContent = "Bidding";
    children.push(heading);
    for (const bid of bids) {
      children.push(text("bid-line", bid));
    }
  }
  element.replaceChildren(...children);
}

/** The status line, and the button that shows the last trick (UI-7, UI-14b). */
function renderStatus(state: GameState): void {
  const element = byId("status");
  if (element === null) {
    return;
  }
  const line = text("status-line", statusLine(state));
  const children: HTMLElement[] = [line];

  if (state.lastTrick !== null && state.gameOver === null) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "last-trick-toggle";
    toggle.textContent = showingLastTrick ? "Hide last trick" : "Show last trick";
    toggle.addEventListener("click", () => {
      showingLastTrick = !showingLastTrick;
      element.dispatchEvent(new CustomEvent("redraw", { bubbles: true }));
    });
    children.push(toggle);
  }
  element.replaceChildren(...children);
}

/** Put this seat's controls on screen, if it has any. */
function renderPanelInto(state: GameState, callbacks: TableCallbacks): void {
  const panel = byId("panel");
  if (panel !== null) {
    renderPanel(panel, state, callbacks);
  }
}

/** Show a rejected action in the server's own words (NFR-4). */
export function showError(message: string): void {
  const element = byId("toast");
  if (element === null) {
    return;
  }
  element.textContent = message;
  element.hidden = false;
  window.setTimeout(() => {
    element.hidden = true;
  }, 4000);
}

/** Stop showing the last trick — called when the next one is cleared. */
export function hideLastTrick(): void {
  showingLastTrick = false;
}

/** A span with a class and some text. */
function text(className: string, content: string): HTMLElement {
  const element = document.createElement("span");
  element.className = className;
  element.textContent = content;
  return element;
}

/** A seat's name, for a label inside the table. */
function nameFor(state: GameState, playerId: string): string {
  return state.seats.find((seat) => seat.playerId === playerId)?.name ?? playerId;
}

/** One of the page's named containers. */
function byId(id: string): HTMLElement | null {
  return document.getElementById(id);
}
