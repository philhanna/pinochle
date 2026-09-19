// The raw frame log.
//
// Phase A's entire view: it shows what the server said, in order, with no
// interpretation at all. That is the point — the transport contract is being
// reviewed here, so nothing should stand between the wire and the screen.
// The table itself arrives in Phase C.

import type { Frame } from "./types.js";

/** The handle a caller uses to drive the log view. */
export interface LogView {
  append: (frame: Frame) => void;
  note: (message: string, kind?: "info" | "error") => void;
}

/** Build the log view inside `root` and return its handle. */
export function createLog(root: HTMLElement): LogView {
  const status = element("div", "status");
  const frames = element("ol", "frames");
  const received: Frame[] = [];

  root.replaceChildren(status, copyButton(received), frames);
  renderStatus(status, null);

  return {
    append(frame: Frame) {
      received.push(frame);
      renderStatus(status, frame);
      frames.append(renderFrame(frame));
      frames.lastElementChild?.scrollIntoView({ block: "nearest" });
    },
    note(message: string, kind: "info" | "error" = "info") {
      const line = element("li", `note ${kind}`);
      line.textContent = message;
      frames.append(line);
      line.scrollIntoView({ block: "nearest" });
    },
  };
}

/** Create an element with a class, the one bit of DOM boilerplate worth naming. */
function element(tag: string, className: string): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  return node;
}

/**
 * A button that copies every frame received so far as JSON.
 *
 * This is how a recorded game gets out of the browser and into the reducer's
 * replay test (docs/impl.md B1), so it is worth the six lines.
 */
function copyButton(received: Frame[]): HTMLElement {
  const button = element("button", "copy");
  button.textContent = "Copy frames as JSON";
  button.addEventListener("click", () => {
    void navigator.clipboard.writeText(JSON.stringify(received, null, 2));
    button.textContent = `Copied ${received.length} frames`;
    window.setTimeout(() => (button.textContent = "Copy frames as JSON"), 1500);
  });
  return button;
}

/** Redraw the one-line summary of where the game currently is. */
function renderStatus(status: HTMLElement, frame: Frame | null): void {
  if (frame === null) {
    status.textContent = "Connecting…";
    return;
  }
  const { phase, current_player_id, paused, round_number } = frame.turn;
  const parts = [
    `round ${round_number}`,
    `phase ${phase}`,
    `turn ${current_player_id ?? "—"}`,
    paused === null ? "running" : `paused: ${paused}`,
    `seq ${frame.seq}`,
  ];
  status.textContent = parts.join("  ·  ");
}

/** Render one frame as a list item: sequence number, name, payload. */
function renderFrame(frame: Frame): HTMLElement {
  const item = element("li", `frame ${frame.type}`);
  const name = element("span", "name");
  name.textContent = `${frame.seq}  ${frame.type}`;
  const payload = element("pre", "payload");
  payload.textContent = JSON.stringify(frame.payload);
  item.append(name, payload);
  return item;
}
