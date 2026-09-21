// Talking to the administrative API.

/** A failed request, carrying the server's own error code and message. */
export class ApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

/** One seat as the create-game response describes it. */
export interface SeatResult {
  seat: string;
  name: string;
  type: string;
  player_id: string;
  join_url: string | null;
}

/** The result of creating a game. */
export interface CreatedGame {
  game_id: string;
  seats: SeatResult[];
}

/** One seat's setup status, as the status endpoint reports it.
 *
 * `join_url` is not part of that response — a token is shown once, at
 * creation, and cannot be retrieved afterwards. The console carries it
 * forward here so a refreshed row keeps the link it was given.
 */
export interface SeatStatus {
  seat: string;
  player_id: string;
  name: string;
  type: string;
  joined: boolean;
  join_url?: string | null;
}

/** What the administrator asks for when creating a game. */
export interface GameSetup {
  teams: { ns: string; ew: string };
  seats: { seat: string; name: string; type: string }[];
}

/** What the console's setup form starts out holding, from the server's config. */
export interface TableDefaults {
  teams: { ns: string; ew: string };
  seats: { seat: string; name: string; type: string }[];
}

/**
 * Return the table the setup form should be pre-filled with (§10.4).
 *
 * Behind the admin token like every other console call, so the console can
 * only ask once it has one.
 */
export async function getDefaults(adminToken: string): Promise<TableDefaults> {
  return (await send(adminToken, "GET", "/api/admin/defaults")) as TableDefaults;
}

/** Create a game and seat all four players (FR-6, FR-7). */
export async function createGame(adminToken: string, setup: GameSetup): Promise<CreatedGame> {
  return (await send(adminToken, "POST", "/api/admin/games", setup)) as CreatedGame;
}

/** Return each seat's setup status, including which human seats have joined. */
export async function getStatus(adminToken: string, gameId: string): Promise<SeatStatus[]> {
  const body = await send(adminToken, "GET", `/api/admin/games/${encodeURIComponent(gameId)}`);
  return (body as { seats: SeatStatus[] }).seats;
}

/** Begin dealer selection (FR-9). Refused until every human seat has joined. */
export async function startGame(adminToken: string, gameId: string): Promise<void> {
  await send(adminToken, "POST", `/api/admin/games/${encodeURIComponent(gameId)}/start`);
}

/** End a game that cannot be completed, revoking its seat tokens. */
export async function abandonGame(
  adminToken: string, gameId: string, reason: string,
): Promise<void> {
  await send(
    adminToken, "POST", `/api/admin/games/${encodeURIComponent(gameId)}/abandon`, { reason },
  );
}

/**
 * Send one administrative request and return its decoded body.
 *
 * The token goes in the header, never the query string: only the read-only
 * stream accepts it there. Failures arrive as the server's
 * `{"error": {"code", "message"}}` envelope, which becomes an `ApiError` so
 * that callers show the server's own wording rather than inventing their own.
 */
async function send(
  adminToken: string, method: string, path: string, body?: unknown,
): Promise<unknown> {
  const response = await fetch(path, {
    method,
    headers: {
      "X-Admin-Token": adminToken,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });

  if (response.status === 204) {
    return {};
  }

  const text = await response.text();
  const parsed: unknown = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const error = (parsed as { error?: { code?: string; message?: string } }).error;
    throw new ApiError(
      error?.code ?? String(response.status),
      error?.message ?? `Request failed with ${response.status}.`,
    );
  }
  return parsed;
}
