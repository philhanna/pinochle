// The SSE connection.

import { FRAME_TYPES, type Frame, type Seat } from "./types.js";

/** What a caller must supply to be driven by the stream. */
export interface StreamHandlers {
  onFrame: (frame: Frame) => void;
  onError: (message: string) => void;
}

/** The URL of a seat's own event stream. */
export function playerStreamUrl(seat: Seat): string {
  const path = `/api/games/${encodeURIComponent(seat.gameId)}/stream`;
  return `${path}?t=${encodeURIComponent(seat.token)}`;
}

/**
 * The URL of the administrator's stream: public events only.
 *
 * The token goes in the query string because `EventSource` cannot set the
 * `X-Admin-Token` header. Only this read-only route accepts it that way;
 * every admin command still requires the header.
 */
export function adminStreamUrl(gameId: string, adminToken: string): string {
  const path = `/api/admin/games/${encodeURIComponent(gameId)}/stream`;
  return `${path}?t=${encodeURIComponent(adminToken)}`;
}

/**
 * Open the stream at `url` and deliver every frame to `handlers`.
 *
 * The server names each frame on its `event:` line, and `EventSource` has no
 * wildcard, so every name in `FRAME_TYPES` is subscribed individually.
 *
 * No reconnection is attempted, and the server has already set a one-day
 * retry to stop `EventSource` trying on its own: there is nothing a
 * reconnect could rebuild, because the server keeps no snapshot of a game in
 * progress (RT-5).
 */
export function openStream(url: string, handlers: StreamHandlers): EventSource {
  const source = new EventSource(url);

  for (const type of FRAME_TYPES) {
    source.addEventListener(type, (event) => {
      const frame = parseFrame(event as MessageEvent<string>);
      if (frame === null) {
        handlers.onError(`Unparseable ${type} frame.`);
      } else {
        handlers.onFrame(frame);
      }
    });
  }

  source.addEventListener("error", () => {
    // Indistinguishable here from the server closing a finished game's
    // stream; the caller decides how to say so.
    handlers.onError(
      source.readyState === EventSource.CLOSED
        ? "Stream closed. This seat cannot rejoin (RT-5); open a new game."
        : "Stream interrupted.",
    );
  });

  return source;
}

/**
 * Decode one frame's JSON, or null if it is not a frame at all.
 *
 * `EventSource` cannot set request headers, which is why the token travels
 * in the query string; it also gives no way to see a non-200 response, so a
 * rejected token surfaces only as an error event.
 */
function parseFrame(event: MessageEvent<string>): Frame | null {
  try {
    const frame = JSON.parse(event.data) as Frame;
    return typeof frame.seq === "number" && typeof frame.type === "string" ? frame : null;
  } catch {
    return null;
  }
}
