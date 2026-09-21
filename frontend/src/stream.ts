// The SSE connection.

import { FRAME_TYPES, type Frame, type Seat } from "./types.js";

/**
 * Whether this client is currently being told what happens at the table.
 *
 * `"down"` is the one that matters: the connection has dropped and the
 * browser is retrying. The table on screen is frozen at whatever it last
 * heard, so it is no longer a picture of the game, and nothing this seat
 * does can be trusted to mean what it appears to mean.
 */
export type ConnectionState = "connecting" | "live" | "down" | "closed";

/** What a caller must supply to be driven by the stream. */
export interface StreamHandlers {
  onFrame: (frame: Frame) => void;
  onError: (message: string) => void;
  /** Called on every change of connection state, if the caller cares. */
  onConnection?: (connection: ConnectionState) => void;
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
 * A dropped connection is recoverable (RT-5a): `EventSource` retries on the
 * server's short `retry:` interval, sending back the last `id:` it saw, and
 * the server replays what this seat missed. Until that succeeds the caller
 * is told the stream is `"down"`, because a frozen table that still looks
 * live is the worst of the three things this can do.
 */
export function openStream(url: string, handlers: StreamHandlers): EventSource {
  const source = new EventSource(url);
  const report = (connection: ConnectionState) => handlers.onConnection?.(connection);

  report("connecting");
  source.addEventListener("open", () => report("live"));

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
    // CLOSED means the browser has given up — a rejected token, or a server
    // that will not have it. Anything else is a drop it is already retrying,
    // and those are expected: a laptop lid, a dozing wifi radio.
    if (source.readyState === EventSource.CLOSED) {
      report("closed");
      handlers.onError("Connection refused. Reopen this seat's join link.");
    } else {
      report("down");
    }
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
