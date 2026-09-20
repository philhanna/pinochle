// Resolving which seat this tab is playing.

import type { Seat } from "./types.js";

/**
 * Return the seat this tab is playing, or null if the page was opened
 * without a join link.
 *
 * The token is read from the `?t=` query parameter of a join link and
 * mirrored into `sessionStorage`, so a reload keeps the seat even though the
 * server mints a token once and cannot reissue it.
 *
 * `sessionStorage`, never `localStorage`: storage is scoped to the origin,
 * so four seats opened as four tabs of one browser — the only way to watch a
 * whole table on one machine — would otherwise overwrite each other's token
 * and collapse into a single seat. `sessionStorage` is per tab, so they stay
 * four distinct seats (docs/impl.md D1).
 */
export function resolveSeat(url: URL = new URL(window.location.href)): Seat | null {
  const gameId = gameIdFromPath(url.pathname);
  if (gameId === null) {
    return null;
  }
  const token = tokenFor(gameId, url.searchParams.get("t"));
  return token === null ? null : { gameId, token };
}

/** Extract the game id from a `/join/{gameId}` path. */
function gameIdFromPath(pathname: string): string | null {
  const match = /^\/join\/([^/]+)\/?$/.exec(pathname);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

/**
 * Return the token for `gameId`, preferring the one in the link.
 *
 * The token is left in the address bar rather than stripped: a tab closed
 * and reopened starts with an empty `sessionStorage`, and the join link is
 * the only copy of a token that exists.
 */
function tokenFor(gameId: string, fromQuery: string | null): string | null {
  const key = `pinochle.seat.${gameId}`;
  if (fromQuery) {
    try {
      window.sessionStorage.setItem(key, fromQuery);
    } catch {
      // Private windows and blocked site data throw here; the token in the
      // URL is enough to play, it just will not survive a reload.
    }
    return fromQuery;
  }
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

const ADMIN_KEY = "pinochle.admin";

/**
 * Return the admin token for the console: from `?t=`, else from this tab.
 *
 * A console link carries the token the way a join link does, so an operator
 * opens a URL rather than copying a credential into a field — which is the
 * difference between the console working first time and answering "Bad admin
 * token." The token is only read here and sent in a header; no mutating
 * endpoint accepts one from a query string.
 */
export function resolveAdminToken(url: URL = new URL(window.location.href)): string {
  const fromQuery = url.searchParams.get("t");
  if (fromQuery) {
    rememberAdminToken(fromQuery);
    return fromQuery;
  }
  return storedAdminToken();
}

/**
 * Return the admin token entered earlier in this tab, or the empty string.
 *
 * `sessionStorage` again, and for a second reason beyond the one in
 * `resolveSeat`: an administrative credential that outlived the tab would sit
 * in a shared browser until someone cleared it.
 */
export function storedAdminToken(): string {
  try {
    return window.sessionStorage.getItem(ADMIN_KEY) ?? "";
  } catch {
    return "";
  }
}

/** Remember the admin token for the rest of this tab's session. */
export function rememberAdminToken(token: string): void {
  try {
    window.sessionStorage.setItem(ADMIN_KEY, token);
  } catch {
    // Blocked site data: the console still works, it just asks again on reload.
  }
}
