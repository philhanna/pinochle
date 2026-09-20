// Entry point for the player's page.

import { createLog } from "./log.js";
import { openStream, playerStreamUrl } from "./stream.js";
import { resolveSeat } from "./token.js";

main();

/**
 * Connect this tab's seat to its event stream and log everything it says.
 *
 * Phase A only: there is no table, no input, and no interpretation of the
 * frames, so that the transport contract can be reviewed on its own.
 */
function main(): void {
  const root = document.getElementById("app");
  if (root === null) {
    return;
  }

  const seat = resolveSeat();
  if (seat === null) {
    showJoinInstructions(root);
    return;
  }

  const log = createLog(root);
  openStream(playerStreamUrl(seat), {
    onFrame: (frame) => log.append(frame),
    onError: (message) => log.note(message, "error"),
  });
}

/** Explain how to get a join link, for a page opened at `/` with no token. */
function showJoinInstructions(root: HTMLElement): void {
  const message = document.createElement("p");
  message.className = "note info";
  message.textContent =
    "No seat. Open a join link from the admin console at /admin — " +
    "each seat has its own link, and each one belongs in its own tab.";
  root.replaceChildren(message);
}
