#!/usr/bin/env python3
"""Create a game, print its join links, and start it.

Turns the review step of every slice into one command. Uses only the standard
library, so it runs against a container as readily as against a local server.

The server refuses to start a game until every human seat has an open stream
(FR-10b), so by default this waits for the tabs to be opened rather than
failing. An all-computer table has nothing to wait for and starts at once.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

SEATS = ["NORTH", "EAST", "SOUTH", "WEST"]
NAMES = {"NORTH": "North", "EAST": "East", "SOUTH": "South", "WEST": "West"}


def main(argv: list[str] | None = None) -> int:
    """Create the game, print the links, wait for the humans, start it."""
    args = parse_args(argv)
    humans = parse_humans(args.humans)

    try:
        game = create_game(args.base, args.token, humans)
    except urllib.error.URLError as exc:
        print(f"Could not reach {args.base}: {reason(exc)}", file=sys.stderr)
        print("Is the server running?  Try: make dev", file=sys.stderr)
        return 1

    game_id = game["game_id"]
    print_seats(game_id, game["seats"])

    if args.no_start:
        print("Not started (--no-start).")
        return 0

    # Worth waiting only because a start follows it; --no-start returns above.
    if humans and not args.no_wait:
        if not wait_for_humans(args.base, args.token, game_id, args.timeout):
            print(
                f"\nStill waiting after {args.timeout}s. Open the links above, "
                f"then start the game from the console.",
                file=sys.stderr,
            )
            return 1

    start_game(args.base, args.token, game_id)
    print("Started.")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--humans", default="SOUTH",
        help='Comma-separated seats to make human, or "none" (default: SOUTH).',
    )
    parser.add_argument("--base", default="http://localhost:8000", help="Server base URL.")
    parser.add_argument("--token", default="dev", help="Admin token (default: dev).")
    parser.add_argument(
        "--no-wait", action="store_true",
        help="Do not wait for human seats to join before starting.",
    )
    parser.add_argument("--no-start", action="store_true", help="Create and seat only.")
    parser.add_argument(
        "--timeout", type=float, default=120.0,
        help="Seconds to wait for human seats to join (default: 120).",
    )
    return parser.parse_args(argv)


def parse_humans(spec: str) -> list[str]:
    """Return the seats named by ``spec``, validating each one."""
    if spec.strip().lower() in ("none", ""):
        return []
    seats = [s.strip().upper() for s in spec.split(",")]
    unknown = [s for s in seats if s not in SEATS]
    if unknown:
        raise SystemExit(f"Not a seat: {', '.join(unknown)}. Use {'/'.join(SEATS)}.")
    return seats


def create_game(base: str, token: str, humans: list[str]) -> dict:
    """POST the game and its four seats, returning the response body."""
    body = {
        "teams": {"ns": "North-South", "ew": "East-West"},
        "seats": [
            {
                "seat": seat,
                "name": NAMES[seat] if seat in humans else f"{NAMES[seat]} (cpu)",
                "type": "human" if seat in humans else "computer",
            }
            for seat in SEATS
        ],
    }
    return request(base, token, "POST", "/api/admin/games", body)


def print_seats(game_id: str, seats: list[dict]) -> None:
    """Print the seat table, with a join link for each human seat."""
    print(f"game {game_id}\n")
    for seat in seats:
        label = f"  {seat['seat']:<6} {seat['name']:<14} {seat['type']:<9}"
        print(f"{label} {seat['join_url'] or '-'}")
    print()


def wait_for_humans(base: str, token: str, game_id: str, timeout: float) -> bool:
    """Poll seat status until every human seat has an open stream.

    Returns False on timeout. Polling here is a convenience for the operator
    and is not how clients learn anything (RT-2 forbids that); the game state
    itself still only ever reaches a client by push.
    """
    print("Waiting for human seats to open their links (Ctrl-C to skip)…", end="", flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = request(base, token, "GET", f"/api/admin/games/{game_id}")
        missing = [s["seat"] for s in status["seats"] if not s["joined"]]
        if not missing:
            print(" all joined.")
            return True
        time.sleep(1.0)
        print(".", end="", flush=True)
    return False


def start_game(base: str, token: str, game_id: str) -> None:
    """POST the start command."""
    request(base, token, "POST", f"/api/admin/games/{game_id}/start")


def request(base: str, token: str, method: str, path: str, body: dict | None = None) -> dict:
    """Send one admin request, returning the decoded body (``{}`` for a 204)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={"X-Admin-Token": token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {path} failed: {exc.code} {exc.read().decode()[:300]}") from None


def reason(exc: urllib.error.URLError) -> str:
    """Return the readable half of a connection failure."""
    return str(getattr(exc, "reason", exc))


if __name__ == "__main__":
    raise SystemExit(main())
