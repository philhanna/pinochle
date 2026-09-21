#!/usr/bin/env python3
"""Check that every control on the table can actually be clicked.

The client's own tests run under ``node --test``, which has no DOM and no
layout engine, so they cannot see a control that is drawn correctly, enabled
correctly, and covered by something else.  That is not a theoretical gap: the
trick layer is a fixed 300x260 box from the moment a round starts, and when
the cards were enlarged it came to rest exactly on top of the contract
panel's buttons.  Clicking Play did nothing whatsoever -- no move, no error,
no request -- because no handler ever ran.

So this drives a real browser: ``frontend/test/browser/reachability.html``
replays the recorded seat stream through the real reducer and the real
renderer against the real stylesheet, and asks, after every frame, what a
click aimed at each control would actually hit.

Needs Chrome, which is why it is its own target (``make test-browser``)
rather than part of ``make test``.
"""
import argparse
import html
import http.server
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
PAGE = "/test/browser/reachability.html"

# Browsers this knows how to drive, in the order it looks for them.
CHROMES = ("google-chrome", "chromium", "chromium-browser", "chrome")

# One window per size.  The layout is a fixed stage scaled to fit (UI-17), so
# the geometry is the same at every size and one would do; the others are here
# because "the same" is exactly the assumption worth testing.
SIZES = ("1600x1100", "1200x900", "900x700")

# Controls the recorded stream must exercise, so that a run which quietly
# stopped rendering is a failure rather than a pass with nothing checked.
REQUIRED = ("#panel button", "#hand .card", ".trick")


def main(argv: list[str] | None = None) -> int:
    """Probe every window size, and report what could not be clicked."""
    args = parse_args(argv)
    chrome = find_chrome(args.chrome)
    if chrome is None:
        print(
            f"No browser found (looked for: {', '.join(CHROMES)}).  "
            "Install one, or pass --chrome.", file=sys.stderr,
        )
        return 2

    failed = False
    with serve(FRONTEND) as port:
        for size in args.sizes:
            result = probe(chrome, port, size, args.timeout)
            failed |= not check(size, result)
    if not failed:
        print("Every control is reachable at every size.")
    return 1 if failed else 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--chrome", help="Browser binary to use, if it is not on the PATH.",
    )
    parser.add_argument(
        "--size", dest="sizes", action="append", metavar="WxH",
        help=f"Window size to test; repeatable (default: {', '.join(SIZES)}).",
    )
    parser.add_argument(
        "--timeout", type=float, default=120.0,
        help="Seconds to allow one browser run (default: 120).",
    )
    args = parser.parse_args(argv)
    args.sizes = args.sizes or list(SIZES)
    return args


def find_chrome(override: str | None) -> str | None:
    """Return the browser to drive, or None if there isn't one."""
    if override:
        return override
    for name in CHROMES:
        found = shutil.which(name)
        if found:
            return found
    return None


@contextmanager
def serve(directory: Path):
    """Serve ``directory`` on a free local port for the duration of the block.

    Over HTTP rather than ``file://`` because the harness is an ES module and
    fetches the page and the fixture, both of which a file URL forbids.
    """
    handler = _quiet_handler(directory)
    with socket.socket() as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        port = probe_socket.getsockname()[1]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()


def probe(chrome: str, port: int, size: str, timeout: float) -> dict:
    """Run the harness in one browser window, and return what it reported."""
    width, _, height = size.partition("x")
    with tempfile.TemporaryDirectory() as profile:
        command = [
            chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
            # Never touch the caller's real browser profile.
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            # Let the replay finish before the DOM is dumped.
            "--virtual-time-budget=30000",
            "--dump-dom", f"http://127.0.0.1:{port}{PAGE}",
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout,
            )
        except FileNotFoundError:
            return {"error": f"cannot run {chrome}"}
        except subprocess.TimeoutExpired:
            return {"error": f"{chrome} did not finish within {timeout:g}s"}
    return extract(completed.stdout)


def extract(dom: str) -> dict:
    """Return the JSON the harness left in its result element."""
    match = re.search(r'<pre id="result">(.*?)</pre>', dom, re.DOTALL)
    if match is None:
        return {"error": "the harness left no result in the page"}
    text = html.unescape(match.group(1))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": f"unreadable result: {text[:200]}"}


def check(size: str, result: dict) -> bool:
    """Report one window's result, and say whether it passed."""
    if "error" in result:
        print(f"{size}: {result['error']}", file=sys.stderr)
        return False

    checked = result.get("checked", {})
    missing = [selector for selector in REQUIRED if selector not in checked]
    if missing:
        print(
            f"{size}: nothing to check for {', '.join(missing)} -- the replay "
            "did not reach them, so this run proves nothing.", file=sys.stderr,
        )
        return False

    blocked = result.get("blocked", [])
    counts = ", ".join(f"{k} x{v}" for k, v in sorted(checked.items()))
    print(f"{size}: {result.get('frames')} frames, {counts}")
    for entry in blocked:
        print(
            f"  BLOCKED {entry['control']} "
            f"{'(' + entry['label'] + ') ' if entry['label'] else ''}"
            f"by {entry['blocker']} "
            f"at frame {entry['frame']} ({entry['type']}, {entry['phase']})",
            file=sys.stderr,
        )
    return not blocked


def _quiet_handler(directory: Path):
    """A request handler rooted at ``directory`` that logs nothing."""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, *args):
            """Say nothing: the browser's own requests are not the output."""

    return Handler


if __name__ == "__main__":
    sys.exit(main())
