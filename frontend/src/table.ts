// Drawing the table.
//
// One function renders the whole thing from the state, because the state is
// the only model there is (RT-5) and a redraw is cheap at this size. The
// exceptions are the two things a pointer can be holding — a card in the hand
// and a card in the spread — which must not be pulled out from under it.

import { backUrl, faceUrl } from "./cards.js";
import { DEAL_PACKET_MS, dealOrder } from "./deal.js";
import { backsFan, droppedCard, isDragging, markResorted, renderHand } from "./hand.js";
import {
  isPaused, placement, playHasBegun, suitGlyph, trickCards, type Spot,
} from "./layout.js";
import { renderPanel, type PanelCallbacks } from "./panels.js";
import { notice } from "./notice.js";
import { isMovingCard, renderSpread } from "./spread.js";
import type { GameState } from "./state.js";
import type { ConnectionState } from "./stream.js";
import {
  bidCall, bidHistory, gameOverText, meldIsExposed, meldLines, scoreboard, seatLabel,
  statusLine, summaryHeadline, summaryRows, trumpText, winningBidText,
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
export function renderTable(
  state: GameState, callbacks: TableCallbacks, dealPacket: number | null = null,
): void {
  renderSeats(state);
  renderDealFlight(state, dealPacket);
  renderSpreadInto(state, callbacks);
  renderCentre(state, callbacks);
  renderScoreboard(state);
  renderContract(state);
  renderTrump(state);
  renderNotice(state, callbacks);
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

/** Keep the auction winner and contract amount visible in the lower-left. */
function renderContract(state: GameState): void {
  const element = byId("contract-indicator");
  if (element === null) {
    return;
  }
  const contract = winningBidText(state);
  element.textContent = contract;
  element.hidden = contract === "";
}

const DEAL_SOURCE = {
  top: [50, 7],
  left: [5, 46],
  right: [95, 46],
  bottom: [50, 95],
} as const;

const DEAL_TARGET = {
  top: [50, 23],
  left: [16, 46],
  right: [84, 46],
  bottom: [50, 79],
} as const;

const STAGE_WIDTH = 1420;
const STAGE_HEIGHT = 1000;

/** A bowed quadratic path, rather than two straight runs through the centre. */
function dealArc(from: readonly [number, number], to: readonly [number, number]): string {
  const start = [from[0] * STAGE_WIDTH / 100, from[1] * STAGE_HEIGHT / 100] as const;
  const end = [to[0] * STAGE_WIDTH / 100, to[1] * STAGE_HEIGHT / 100] as const;
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  const distance = Math.hypot(dx, dy);
  const bow = Math.min(180, distance * 0.22);
  const controlX = (start[0] + end[0]) / 2 - (dy / distance) * bow;
  const controlY = (start[1] + end[1]) / 2 + (dx / distance) * bow;
  return `path("M ${start[0]} ${start[1]} Q ${controlX} ${controlY} ${end[0]} ${end[1]}")`;
}

/** Send one visible three-card packet from the dealer to its recipient. */
function renderDealFlight(state: GameState, packetIndex: number | null): void {
  const root = byId("deal-flight");
  if (root === null) {
    return;
  }
  const spots = placement(state);
  const spotFor = (playerId: string | null): Spot | null => {
    for (const spot of ["bottom", "left", "top", "right"] as const) {
      if (spots[spot]?.playerId === playerId) {
        return spot;
      }
    }
    return null;
  };
  const order = dealOrder(state);
  const recipientId = packetIndex === null || order.length === 0
    ? null
    : order[packetIndex % order.length] ?? null;
  const from = spotFor(state.dealerPlayerId);
  const to = spotFor(recipientId);
  if (packetIndex === null || from === null || to === null) {
    root.replaceChildren();
    root.hidden = true;
    return;
  }

  const packet = document.createElement("div");
  packet.className = "deal-packet";
  packet.style.animationDuration = `${DEAL_PACKET_MS}ms`;
  packet.style.offsetPath = dealArc(DEAL_SOURCE[from], DEAL_TARGET[to]);
  for (let cardIndex = 0; cardIndex < 3; cardIndex += 1) {
    const card = document.createElement("img");
    card.className = "deal-card";
    card.src = backUrl();
    card.alt = "";
    card.style.setProperty("--packet-card", String(cardIndex));
    packet.append(card);
  }
  root.replaceChildren(packet);
  root.hidden = false;
}

/** Keep the named trump visible in the lower-right corner of the table. */
function renderTrump(state: GameState): void {
  const element = byId("trump-indicator");
  if (element === null) {
    return;
  }
  if (state.trump === null) {
    element.textContent = "";
    element.className = "";
    element.hidden = true;
    return;
  }

  const { red } = suitGlyph(state.trump);
  element.textContent = trumpText(state);
  element.className = red ? "red" : "black";
  element.hidden = false;
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
    // The card this seat drew for the deal sits in front of them, face up,
    // where their hand is about to be (FR-11d, FR-15).
    const drawn = drawnBy(state, seat.playerId);
    if (drawn !== null) {
      children.push(drawnCard(drawn));
    }
    if (spot !== "bottom") {
      const count = state.handCounts[seat.playerId] ?? 0;
      children.push(backsFan(count, spot === "left" || spot === "right"));
    }
    const meld = state.phase === "MELDING" ? state.meld[seat.playerId] : undefined;
    if (meld !== undefined && meld.units.length > 0) {
      children.push(meldGroups(meld.units));
    }
    const call = bidCall(state, seat.playerId);
    if (call !== null) {
      children.push(text("bid-call", call));
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

/** The public cards one player has laid out, separated by meld combination. */
function meldGroups(units: GameState["meld"][string]["units"]): HTMLElement {
  const shelf = document.createElement("div");
  shelf.className = "meld-cards";
  for (const unit of units) {
    const group = document.createElement("div");
    group.className = "meld-group";

    const cards = document.createElement("div");
    cards.className = "meld-group-cards";
    for (const card of unit.cards ?? []) {
      const image = document.createElement("img");
      image.className = "meld-card";
      image.src = faceUrl(card);
      image.alt = card;
      cards.append(image);
    }

    const label = document.createElement("div");
    label.className = "meld-group-label";
    label.textContent = `${unit.name} · ${unit.points}`;
    group.append(cards, label);
    shelf.append(group);
  }
  return shelf;
}

/**
 * What a seat drew for the deal, while the deal is still being settled.
 *
 * Only while it is: once the round starts, every seat has a hand, and the
 * card that won the deal is back in the deck with the rest.
 */
function drawnBy(state: GameState, playerId: string): string | null {
  if (state.phase !== "DEALER_SELECTION") {
    return null;
  }
  return state.draws.find((draw) => draw.playerId === playerId)?.card ?? null;
}

/** A drawn card, face up in front of a seat (FR-11d). */
function drawnCard(card: string): HTMLElement {
  const image = document.createElement("img");
  image.className = "card small drawn";
  image.src = faceUrl(card);
  image.alt = card;
  return image;
}

/** The scattered spread, which a drag must not have pulled away (FR-11c). */
function renderSpreadInto(state: GameState, callbacks: TableCallbacks): void {
  const element = byId("spread");
  // A redraw mid-drag would destroy the card under the pointer, so the spread
  // waits; letting go of the card asks for the redraw it missed.
  if (element !== null && !isMovingCard()) {
    renderSpread(element, state, callbacks);
  }
}

/** The middle of the table: the trick, or a panel about the round. */
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
    // The spread is not in the middle of the table but strewn across it, so
    // the middle holds nothing — and must hold nothing, since the trick
    // layer's box is invisible, is drawn whether or not a card has been
    // played, and would lie over the cards and take their clicks (UI-18).
    centre.replaceChildren();
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

/**
 * What this seat passed or received, shown to its team alone (UI-12, RT-1).
 *
 * Received cards join the hand, where they are indistinguishable from the rest;
 * a player needs to see which four arrived. It comes down when the first trick
 * may be led: by then it has been read, and what the table needs from that
 * moment on is the room to play in.
 */
function passPanel(state: GameState): HTMLElement | null {
  const received = state.received;
  const sent = state.sent;
  if ((received === null && sent === null) || state.phase === "MELDING" || playHasBegun(state)) {
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

/**
 * What the table has just been told, and the control that moves it on.
 *
 * The words come from `notice`, which is pure; this only puts them on screen
 * and hangs a button off them when the game is being held (UI-19, UI-19a).
 * Any seat may use that button, so nothing here asks whose turn it is.
 *
 * Rebuilt only when the notice actually changes. Every frame carries the turn
 * header and so produces a notice, but most produce the same one, and
 * replacing the button under a pointer that is on its way to it is a good way
 * to lose the click.
 */
function renderNotice(state: GameState, callbacks: TableCallbacks): void {
  const element = byId("notice");
  if (element === null) {
    return;
  }
  const shown = notice(state);
  if (shown === null) {
    renderedNotice = null;
    element.replaceChildren();
    element.hidden = true;
    return;
  }

  const signature = `${shown.key}|${shown.text}|${shown.release ?? ""}`;
  element.className = shown.kind;
  element.hidden = false;
  if (signature === renderedNotice) {
    return;
  }
  renderedNotice = signature;

  const children: HTMLElement[] = [text("notice-line", shown.text)];
  if (shown.release !== null) {
    const release = shown.release;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "notice-continue";
    button.textContent = "Continue";
    button.addEventListener("click", () => callbacks.onAcknowledge(release));
    children.push(button);
  }
  element.replaceChildren(...children);
}

/** What the notice area is currently showing, so a redraw leaves it alone. */
let renderedNotice: string | null = null;

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

/**
 * Say whether this table is still connected, and keep saying it.
 *
 * Deliberately not a toast. A toast that fades leaves a table that looks
 * perfectly normal but is frozen at the last frame it heard, with buttons
 * that quietly do nothing — which is exactly how a dropped connection was
 * reported before, and exactly why it read as a broken Play button. A
 * connection that is down stays on screen until it is not.
 */
export function showConnection(connection: ConnectionState): void {
  const element = byId("connection");
  if (element === null) {
    return;
  }
  const message = CONNECTION_MESSAGES[connection];
  element.textContent = message ?? "";
  element.className = connection;
  element.hidden = message === null;
}

/** What each connection state says, or null for the states that say nothing. */
const CONNECTION_MESSAGES: Record<ConnectionState, string | null> = {
  connecting: null,
  live: null,
  down: "Disconnected — reconnecting. The table is frozen until it comes back.",
  closed: "Disconnected. Reopen this seat's join link to sit down again.",
};

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
