#!/usr/bin/env python3
"""Record one seat's event stream from an all-computer game, as JSON.

Produces the fixture the browser reducer is tested against
(``frontend/test/fixtures/seat-stream.json``). Frames come from the real
service, encoded by the real encoder, so the fixture cannot drift from the
wire format the way a hand-written one would.

Two properties of a seat's stream are reproduced deliberately:

* Only the frames that seat is entitled to — public broadcasts plus its own
  private frames. A hand dealt to another seat never appears.
* Sequence numbers that are monotonic but not contiguous, because the frames
  addressed to other seats consume numbers. A client must tolerate the gaps.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pinochle.adapters.fake_scheduler import FakeScheduler  # noqa: E402
from pinochle.domain.game import GamePhase, RoundScored  # noqa: E402
from pinochle.domain.player import Player, PlayerType, Position  # noqa: E402
from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID, Team  # noqa: E402
from pinochle.web.container import Settings, build_container  # noqa: E402
from pinochle.web.event_encoder import encode_event  # noqa: E402
from pinochle.web.turn_header import build_turn_header  # noqa: E402

SEATS = [
    ("p-north", "North", Position.NORTH),
    ("p-east", "East", Position.EAST),
    ("p-south", "South", Position.SOUTH),
    ("p-west", "West", Position.WEST),
]


def main(argv: list[str] | None = None) -> int:
    """Record a game and write one seat's frames as a JSON array."""
    args = parse_args(argv)
    frames = record(args.seat, args.rounds, args.seed)
    text = json.dumps(frames, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"{len(frames)} frames -> {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seat", default="p-south", help="Whose stream to record.")
    parser.add_argument(
        "--rounds", type=int, default=1,
        help="Stop after this many scored rounds (default: 1).",
    )
    parser.add_argument("--seed", type=int, default=7, help="Shuffle seed (NFR-7).")
    parser.add_argument("--out", help="Write here instead of to stdout.")
    return parser.parse_args(argv)


def record(seat: str, rounds: int, seed: int) -> list[dict]:
    """Play until ``rounds`` rounds have scored, returning ``seat``'s frames."""
    settings = Settings(
        admin_token="record", computer_delay_seconds=0, trick_clear_seconds=0, shuffle_seed=seed,
    )
    scheduler = FakeScheduler()
    container = build_container(settings, scheduler=scheduler)

    game_id = container.admin.create_game()
    container.admin.assign_teams(
        game_id, Team(NS_TEAM_ID, "North-South"), Team(EW_TEAM_ID, "East-West"),
    )
    for player_id, name, position in SEATS:
        container.admin.add_player(
            game_id, Player(player_id, name, PlayerType.COMPUTER, position),
        )

    recorder = SeatRecorder(seat, container, game_id, rounds)
    container.notifier.append(recorder)
    recorder.open_stream()
    container.admin.start_game(game_id)

    for _ in range(200000):
        if recorder.done or container.state.load(game_id).phase == GamePhase.FINISHED:
            break
        scheduler.advance(0)
    return recorder.frames


class SeatRecorder:
    """A ``NotificationPort`` that keeps one seat's frames, decoded to dicts."""

    def __init__(self, seat: str, container, game_id: str, rounds: int):
        """Record for ``seat``, stopping once ``rounds`` rounds have scored."""
        self.seat = seat
        self.container = container
        self.game_id = game_id
        self.rounds_wanted = rounds
        self.rounds_seen = 0
        self.frames: list[dict] = []
        self.seq = 0
        self.done = False

    def open_stream(self) -> None:
        """Record the frame the stream router synthesises when a seat connects."""
        game = self.container.state.load(self.game_id)
        player = game.players[self.seat]
        self.frames.append({
            "seq": 0,
            "type": "stream_started",
            "turn": build_turn_header(game),
            "payload": {
                "seat": player.position.name,
                "player_id": player.id,
                "you": {"name": player.name, "type": player.type.name.lower()},
                "partial": False,
            },
        })

    def broadcast(self, game_id: str, event) -> None:
        """Record a public event, which every seat receives."""
        self._record(event)

    def notify(self, player_id: str, event) -> None:
        """Record a private event only if it is addressed to this seat.

        The sequence number advances either way, which is what puts the gaps
        in a real seat's stream.
        """
        self._record(event, addressed_to=player_id)

    def _record(self, event, addressed_to: str | None = None) -> None:
        """Assign the next sequence number and keep the frame if it is ours."""
        self.seq += 1
        if addressed_to is not None and addressed_to != self.seat:
            return
        game = self.container.state.load(self.game_id)
        raw = encode_event(event, self.seq, build_turn_header(game))
        self.frames.append(json.loads(raw.split("data: ", 1)[1].strip()))
        if isinstance(event, RoundScored):
            self.rounds_seen += 1
            if self.rounds_seen >= self.rounds_wanted:
                self.done = True


if __name__ == "__main__":
    raise SystemExit(main())
