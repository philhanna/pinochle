// Drawing the table.
//
// One function renders the whole thing from the state, because the state is
// the only model there is (RT-5) and a redraw is cheap at this size. The
// exception is the hand during a drag, which must not be pulled out from under
// the pointer.

import { backUrl, faceUrl } from "./cards.js";
import { backsFan, droppedCard, isDragging, markResorted, renderHand } from "./hand.js";
import {
  isPaused, mustDraw, placement, takenPositions, trickCards,
} from "./layout.js";
import { renderPanel, type PanelCallbacks } from "./panels.js";
import type { GameState } from "./state.js";
import {
  bidHistory, gameOverText, meldIsExposed, meldLines, scoreboard, seatLabel,
  statusLine, summaryHeadline, summaryRows,
} from "./view.js";

/** Everything the table can ask of the player. */
export interface TableCallbacks extends PanelCallbacks {
  onDraw: (position: number) => void;
}

/** Whether the last completed trick is being shown (UI-14b). */
let showingLastTrick = false;

/** Whether the scoreboard is open. Closed, it is its own button and no more. */
let scoreboardOpen = true;

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
    if (pendingResort) {
      pendingResort = false;
      markResorted(hand);
    }
  }
}

/** Set when trump is named, so the next redraw can show the hand re-sorting. */
let pendingResort = false;

/** Note that the hand has just been re-ordered by trump being named (FR-23a). */
export function noteResort(): void {
  pendingResort = true;
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

/** The middle of the table: the spread, the trick, or a summary. */
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
  const pass = passPanel(state);
  centre.replaceChildren(
    ...(pass === null ? [] : [pass]), trickLayer(state, callbacks),
  );
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

/**
 * What this seat passed or received, shown to its team alone (UI-12, RT-1).
 *
 * Received cards join the hand, where they are indistinguishable from the rest;
 * a player needs to see which four arrived. Shown until the trick play starts,
 * at which point it has been read and the table needs the room.
 */
function passPanel(state: GameState): HTMLElement | null {
  const received = state.received;
  const sent = state.sent;
  if ((received === null && sent === null) || state.trick.length > 0) {
    return null;
  }

  const panel = document.createElement("div");
  panel.className = "passed";

  if (received !== null) {
    panel.append(cardRow(`From ${nameFor(state, received.fromPlayerId)}`, received.cards));
  }
  if (sent !== null) {
    panel.append(cardRow(`To ${nameFor(state, sent.toPlayerId)}`, sent.cards));
  }
  return panel;
}

/** A labelled row of small card images. */
function cardRow(label: string, cards: string[]): HTMLElement {
  const row = document.createElement("div");
  row.className = "passed-row";
  row.append(text("passed-label", label));
  const tray = document.createElement("div");
  tray.className = "tray";
  for (const card of cards) {
    const image = document.createElement("img");
    image.className = "card small";
    image.src = faceUrl(card);
    image.alt = card;
    tray.append(image);
  }
  row.append(tray);
  return row;
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

/**
 * The scoreboard: scores, meld, and the bid history (UI-13, UI-14, UI-14a).
 *
 * Everything the round is keeping for the player is here, so there is one
 * place to look rather than a panel in the middle of the table for the meld
 * and a corner for the rest. It opens and closes, because a round's worth of
 * meld and bidding is a tall thing to have standing over the felt.
 */
function renderScoreboard(state: GameState): void {
  const element = byId("scoreboard");
  if (element === null) {
    return;
  }
  element.classList.toggle("open", scoreboardOpen);
  element.replaceChildren(
    ...(scoreboardOpen ? [scoreboardToggle(), scoreboardBody(state)] : [scoreboardToggle()]),
  );
}

/** The scoreboard's own heading, which is also what opens and closes it. */
function scoreboardToggle(): HTMLElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "scoreboard-toggle";
  // Closed, it is the only thing on screen naming what it is, so it is a
  // labelled button and not a bare arrow.
  button.setAttribute("aria-expanded", String(scoreboardOpen));
  button.append(text("scoreboard-title", "Scoreboard"), text("caret", "▾"));
  button.addEventListener("click", () => {
    scoreboardOpen = !scoreboardOpen;
    button.dispatchEvent(new CustomEvent("redraw", { bubbles: true }));
  });
  return button;
}

/**
 * What the scoreboard holds when it is open.
 *
 * The scores run the width of the panel; the meld and the bidding stand side
 * by side beneath them. Two columns because a single one would be twice as
 * tall, and every row of it past the corner hangs over a neighbouring seat.
 */
function scoreboardBody(state: GameState): HTMLElement {
  const body = document.createElement("div");
  body.className = "scoreboard-body";

  const scores = document.createElement("div");
  scores.className = "scores";
  for (const line of scoreboard(state)) {
    const row = document.createElement("div");
    row.className = "score-row";
    row.append(text("score-label", line.label), text("score-value", line.value));
    scores.append(row);
  }
  body.append(scores);

  const meld = meldSection(state);
  if (meld.length > 0) {
    body.append(column(meld));
  }

  const bids = bidHistory(state);
  if (bids.length > 0) {
    body.append(column([heading("Bidding"), ...bids.map((bid) => text("bid-line", bid))]));
  }
  return body;
}

/** One of the two columns under the scores. */
function column(children: HTMLElement[]): HTMLElement {
  const element = document.createElement("div");
  element.className = "score-column";
  element.append(...children);
  return element;
}

/**
 * Each seat's exposed meld (UI-13, UI-14a).
 *
 * While the meld is on the table the combinations are named, not merely
 * totalled: which cards a seat showed is what the other three are entitled to
 * have seen. Once the cards are gathered up the totals stay and the detail
 * goes — both what UI-14a asks for and what keeps this panel from standing
 * over a neighbour's cards for the rest of the round. The first trick gathered
 * to its winner is what marks the meld as taken in.
 *
 * The per-team totals are not repeated here: they are already beside each
 * team's score, which is where UI-14a wants them kept for the round.
 */
function meldSection(state: GameState): HTMLElement[] {
  const lines = meldLines(state);
  if (lines.length === 0) {
    return [];
  }

  const exposed = meldIsExposed(state);
  const children: HTMLElement[] = [heading("Meld")];
  for (const line of lines) {
    children.push(meldRow(line.name, line.total));
    if (exposed) {
      children.push(text("meld-units", line.units.length === 0 ? "no meld" : line.units.join(", ")));
    }
  }
  return children;
}

/** A name and a meld total, on one line. */
function meldRow(name: string, total: number): HTMLElement {
  const row = document.createElement("div");
  row.className = "meld-row";
  row.append(text("meld-who", name), text("meld-total", String(total)));
  return row;
}

/** A small heading inside the scoreboard. */
function heading(label: string): HTMLElement {
  const element = document.createElement("div");
  element.className = "score-heading";
  element.textContent = label;
  return element;
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
