// The administrator's console.
//
// Creates a game, hands out the join links, starts it, and abandons it — plus
// a live view of the public event stream, which for an all-computer table is
// the only way to watch a game at all, since such a table issues no join
// links.

import {
  ApiError,
  abandonGame,
  createGame,
  getDefaults,
  getStatus,
  startGame,
  type CreatedGame,
  type SeatStatus,
  type TableDefaults,
} from "./api.js";
import { createLog, type LogView } from "./log.js";
import { adminStreamUrl, openStream } from "./stream.js";
import { rememberAdminToken, resolveAdminToken } from "./token.js";

const SEATS = ["NORTH", "EAST", "SOUTH", "WEST"] as const;

/** The console's whole state: which game it made, and what it knows of it. */
interface Console_ {
  token: () => string;
  game: CreatedGame | null;
  log: LogView | null;
}

main();

/** Wire the console's controls to the admin API. */
function main(): void {
  const form = document.getElementById("setup") as HTMLFormElement | null;
  const tokenField = document.getElementById("admin-token") as HTMLInputElement | null;
  if (form === null || tokenField === null) {
    return;
  }

  tokenField.value = resolveAdminToken();
  const state: Console_ = { token: () => tokenField.value.trim(), game: null, log: null };

  // The form is born holding the defaults written into admin.html, and asks
  // the server for the operator's own as soon as it can authenticate. A
  // console opened from /admin?t=<token> can do that immediately; one opened
  // bare cannot, so it asks again when a token is typed in.
  void fillDefaults(state, form);
  tokenField.addEventListener("change", () => void fillDefaults(state, form));

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void create(state, form);
  });
  button("start")?.addEventListener("click", () => void start(state));
  button("refresh")?.addEventListener("click", () => void refresh(state));
  button("abandon")?.addEventListener("click", () => void abandon(state));
}

/**
 * Fill the setup form from the server's configured table (§10.4).
 *
 * Quiet about failure on purpose. Wanting the defaults is not the same as
 * wanting to do anything yet, and the operator has not asked for this — a
 * console opened without a token would otherwise greet them with "Bad admin
 * token." before they had touched a control. What is on screen in that case
 * is admin.html's own defaults, which are the same ones the server sends when
 * the environment says nothing.
 */
async function fillDefaults(state: Console_, form: HTMLFormElement): Promise<void> {
  if (state.token() === "") {
    return;
  }
  let defaults: TableDefaults;
  try {
    defaults = await getDefaults(state.token());
  } catch {
    return;
  }

  setField(form, "team-ns", defaults.teams.ns);
  setField(form, "team-ew", defaults.teams.ew);
  for (const seat of defaults.seats) {
    setField(form, `name-${seat.seat}`, seat.name);
    setField(form, `type-${seat.seat}`, seat.type);
  }
}

/** Set one named control's value, if the form has it. */
function setField(form: HTMLFormElement, name: string, value: string): void {
  const field = form.elements.namedItem(name);
  if (field instanceof HTMLInputElement || field instanceof HTMLSelectElement) {
    field.value = value;
  }
}

/** Create the game the form describes, then show its links and stream. */
async function create(state: Console_, form: HTMLFormElement): Promise<void> {
  rememberAdminToken(state.token());
  const data = new FormData(form);

  try {
    state.game = await createGame(state.token(), {
      teams: {
        ns: String(data.get("team-ns") || "North-South"),
        ew: String(data.get("team-ew") || "East-West"),
      },
      seats: SEATS.map((seat) => ({
        seat,
        name: String(data.get(`name-${seat}`) || seat),
        type: String(data.get(`type-${seat}`) || "computer"),
      })),
    });
  } catch (error) {
    return report(error);
  }

  say(`Game ${state.game.game_id} created.`);
  renderSeats(state.game.seats.map(asStatus));
  reveal("game");
  watch(state);
  await refresh(state);
}

/** Show a seat's join link, its kind, and whether it has joined yet. */
function renderSeats(seats: SeatStatus[]): void {
  const rows = document.getElementById("seats");
  if (rows === null) {
    return;
  }

  rows.replaceChildren(...seats.map((seat) => {
    const row = document.createElement("tr");
    row.append(
      cell(seat.seat),
      cell(seat.name),
      cell(seat.type),
      cell(seat.joined ? "joined" : "waiting", seat.joined ? "joined" : "waiting"),
      linkCell(seat),
    );
    return row;
  }));
}

/** One plain table cell. */
function cell(text: string, className = ""): HTMLElement {
  const td = document.createElement("td");
  td.textContent = text;
  td.className = className;
  return td;
}

/**
 * The join-link cell: the link itself, and a button to copy it.
 *
 * A computer seat has no link — nothing is going to open it — so the cell
 * says so rather than showing an empty box.
 */
function linkCell(seat: SeatStatus): HTMLElement {
  const td = document.createElement("td");
  const url = seat.join_url ?? null;
  if (url === null) {
    td.textContent = "—";
    td.className = "waiting";
    return td;
  }

  const link = document.createElement("a");
  link.href = url;
  link.textContent = url;
  link.target = "_blank";
  link.rel = "noopener";

  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "copy";
  copy.textContent = "Copy";
  copy.addEventListener("click", () => {
    void navigator.clipboard.writeText(url);
    copy.textContent = "Copied";
    window.setTimeout(() => (copy.textContent = "Copy"), 1200);
  });

  td.append(link, copy);
  return td;
}

/** Open the administrator's stream and log every public event. */
function watch(state: Console_): void {
  const panel = document.getElementById("events");
  if (panel === null || state.game === null) {
    return;
  }
  state.log = createLog(panel);
  openStream(adminStreamUrl(state.game.game_id, state.token()), {
    onFrame: (frame) => state.log?.append(frame),
    onError: (message) => state.log?.note(message, "error"),
  });
}

/** Ask the server to begin dealer selection. */
async function start(state: Console_): Promise<void> {
  if (state.game === null) {
    return;
  }
  try {
    await startGame(state.token(), state.game.game_id);
    say("Started.");
  } catch (error) {
    // FR-10b: a seat that has not opened its link yet is the usual reason,
    // and the server's message names the seat.
    report(error);
    await refresh(state);
  }
}

/** Re-read seat status, so the table shows who has joined. */
async function refresh(state: Console_): Promise<void> {
  if (state.game === null) {
    return;
  }
  try {
    const status = await getStatus(state.token(), state.game.game_id);
    renderSeats(status.map((seat) => withLink(seat, state.game)));
  } catch (error) {
    report(error);
  }
}

/** Put the join link from creation back onto a refreshed status row. */
function withLink(seat: SeatStatus, game: CreatedGame | null): SeatStatus {
  const created = game?.seats.find((s) => s.seat === seat.seat);
  return { ...seat, ...(created?.join_url ? { join_url: created.join_url } : {}) };
}

/** End the game, revoking its tokens. */
async function abandon(state: Console_): Promise<void> {
  if (state.game === null) {
    return;
  }
  const reason = window.prompt("Why is this game being abandoned?", "Abandoned by the operator");
  if (reason === null) {
    return;
  }
  try {
    await abandonGame(state.token(), state.game.game_id, reason);
    say("Abandoned.");
  } catch (error) {
    report(error);
  }
}

/** Treat a just-created seat as a status row that has not joined yet. */
function asStatus(seat: CreatedGame["seats"][number]): SeatStatus {
  return {
    seat: seat.seat,
    player_id: seat.player_id,
    name: seat.name,
    type: seat.type,
    joined: seat.type === "computer",
    ...(seat.join_url ? { join_url: seat.join_url } : {}),
  };
}

/** Look up one of the console's action buttons. */
function button(id: string): HTMLElement | null {
  return document.getElementById(id);
}

/** Reveal a section that is hidden until there is a game to show in it. */
function reveal(id: string): void {
  const section = document.getElementById(id);
  if (section !== null) {
    section.hidden = false;
  }
}

/** Show a plain message. */
function say(message: string, kind: "info" | "error" = "info"): void {
  const line = document.getElementById("message");
  if (line !== null) {
    line.textContent = message;
    line.className = `note ${kind}`;
  }
}

/** Show a failure in the server's own words. */
function report(error: unknown): void {
  if (error instanceof ApiError && error.code === "forbidden_admin") {
    // The server can only say the token was wrong; it is this page that knows
    // where an operator is supposed to get one.
    say(
      "Bad admin token. The console needs the value of PINOCHLE_ADMIN_TOKEN: "
      + "\"dev\" if the server was started with `make dev`, otherwise the one "
      + "it logged at startup (\"generated one for this run\"). Opening "
      + "/admin?t=<token> fills this in for you.",
      "error",
    );
    return;
  }
  const message = error instanceof ApiError
    ? `${error.message} (${error.code})`
    : error instanceof Error ? error.message : String(error);
  say(message, "error");
}
