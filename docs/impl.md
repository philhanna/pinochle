# Pinochle — Implementation Plan

How the remaining work is broken into reviewable slices, and how each slice is
verified on a single Ubuntu desktop.

`docs/requirements.md` is authoritative; every slice below cites the
requirements it satisfies. This document says only *in what order* and *how
reviewed* — it grants no requirement and waives none.

---

## 1. Where the project stands

Complete and tested (277 tests passing, `pytest`):

- **Domain layer** — cards, deck, hand, bid, meld, trick, scoring, team, game.
- **Ports** — `GameStatePort`, `NotificationPort`, `SeatTokenPort`,
  `CardImagePort`, `SchedulerPort`, `PlayerActionPort`, `AdminPort`.
- **Adapters** — in-memory state and seat tokens, SSE / logging / print /
  composite notification, asyncio + fake + immediate schedulers, SVG card
  images.
- **Services** — game service, round, computer driver, seat view, event
  privacy.
- **Web layer** — FastAPI app, admin router, player router, SSE stream router,
  event encoder, turn header, card codec, error handlers, container/DI.
- **Packaging** — backend-only Docker image and Compose file.

Not started: everything the player sees. There is no `frontend/` tree, so `/`,
`/join/{game_id}` and `/admin` all answer *"The front end has not been built
yet."*

Two known gaps in the server, both folded into slice A1 below:

1. Card artwork is resolvable on disk (`SvgCardImage`) but **not served over
   HTTP**. `/assets` mounts `frontend/public`; nothing mounts
   `pinochle/card_images/`. UI-16 is therefore unmet.
2. `docker/Dockerfile` is backend-only and copies no `frontend/`, and
   `.dockerignore` excludes `frontend/dist`.

---

## 2. Strategy

### 2.1 Drivable before pretty

The riskiest assumption is the transport contract — seat-token auth, the event
vocabulary, and the claim that a client can build its whole view from the event
stream alone with no point-in-time snapshot (RT-5). That must not be debugged
at the same time as CSS.

So **Phase A** builds an ugly but functionally complete client: a raw event log
and one plain HTML form per action. It ends with a full human-vs-computers game
playable end to end, with zero presentation code written.

**Phase B** builds the client state model headless — the one piece everything
renders from, reviewed as code rather than as pixels.

**Phase C** then replaces the debug controls one screen region at a time. Each
Phase C slice is independently reviewable, and none blocks another, because the
debug panel still covers whatever a slice has not reached yet.

### 2.2 One slice, one branch, one review point

Every slice ends with, in order:

1. `make test` green.
2. `make docker` green — the shipped image, played in a container.
3. A written two-line manual check in the slice's own section below, so review
   is a recipe and not a guess.
4. A `CHANGELOG.md` entry.

Version bumps happen at phase boundaries, not per slice: **0.4.0** after Phase
A, **0.5.0** after C1, **1.0.0** after C7.

### 2.3 Everything is local

There is no cloud host and none is needed. Bare `uvicorn` on localhost is the
inner loop; local Docker Compose is the slice gate. Deployment beyond that —
TLS, reverse proxy, real DNS — is deferred (§6).

---

## 3. Decisions locked before Phase A

These are cheap now and expensive later.

- **D1 — Seat tokens live in the URL or `sessionStorage`, never
  `localStorage`.** Four tabs in one browser share origin-scoped
  `localStorage`, so a token kept there means the fourth seat opened overwrites
  the first and single-machine testing becomes impossible. The server already
  accommodates per-tab tokens: `X-Seat-Token` on commands (FR-10a), `?t=` on
  the SSE stream, because `EventSource` cannot set headers.
- **D2 — ES modules, no bundler.** ARC-8 fixes `tsc` with no bundler and no
  runtime dependency, so the client ships as ES modules loaded by
  `<script type="module">`. The module layout is settled in A1 and not
  revisited.
- **D3 — The Docker front-end build stage lands in A1, not at the end.**
  Otherwise bare `uvicorn` would serve the real page while the image served a
  404, and the two run modes would silently disagree for the whole project.
  `frontend/dist` stays in `.dockerignore`: building inside the image is
  exactly what makes the host's stale output irrelevant.
- **D4 — Layout is fixed and scaled to the viewport, from C1.** UI-17 permits
  this instead of a responsive layout. Doing it in C1 is what makes four
  quarter-screen windows tiled 2×2 on one monitor usable, which is the only way
  to watch all four seats at once on one machine.
- **D5 — The client holds no timers that affect what it displays** (RT-8).
  Timed pauses are server state, delimited by events (RT-9, RT-10), and reach
  the client as `paused: "trick_clear" | "thinking" | null` in the turn header.

---

## 4. The wire contract

Every SSE frame is one JSON object:

```json
{ "seq": 41, "type": "card_played", "turn": { … }, "payload": { … } }
```

The `turn` header accompanies *every* frame:

```json
{ "phase": "TRICK_PLAY", "current_player_id": "p2",
  "paused": null, "round_number": 3 }
```

The 22 game event types, in the order a round produces them:

| Phase | Events |
|---|---|
| Setup | `game_configured` |
| Dealer selection | `dealer_selection_started`, `draw_made`, `draw_tied`, `dealer_selected` |
| Deal | `round_started`, `cards_dealt` *(private, NFR-6)* |
| Bidding | `bid_placed`, `contract_offered`, `round_abandoned` |
| Trump & pass | `trump_named`, `cards_passed` *(team-private)* |
| Meld | `meld_exposed` |
| Play | `play_begun`, `contract_tossed_in`, `seat_thinking`, `card_played`, `trick_completed`, `trick_cleared`, `turn_prompt` |
| End | `round_scored`, `game_over` |

Three further types — `seat_lost`, `seat_rejoined`, `game_abandoned` — are
published by the transport rather than the domain. **The client does not handle
them in this plan** (§6).

---

## 5. The slices

### Phase A — end to end drivable

#### A0 · Make the review loop one command

The real cost of solo desktop review is not the machine, it is that every check
starts with "create a game, copy four tokens, open four windows."

- `scripts/dev.sh` — `uvicorn --reload` on localhost, with a fixed
  `PINOCHLE_ADMIN_TOKEN=dev` and an overridable
  `PINOCHLE_COMPUTER_DELAY_SECONDS`.
- `scripts/seed.py` — creates a game with a given human/computer mix, starts
  it, prints the four join URLs ready to paste.
- `Makefile` — `make dev`, `make seed`, `make seed-watch` (four computers, zero
  delay), `make test`, `make docker`.

About eighty lines in total; it pays for itself by C2.

**Check:** `make dev` then `make seed-watch` prints four URLs and the server
log shows a complete all-computer game reaching `game_over`.

#### A1 · Scaffolding, card artwork, Docker stage

- `frontend/` per the split rule: `src/` (TypeScript), `public/`
  (`index.html`, `admin.html`, CSS), `tsconfig.json`, `package.json`. Nothing
  browser-side goes in `pinochle/`.
- An `EventSource` client that connects with `?t=` and appends each raw frame
  to a `<pre>`.
- **Gap 1:** serve `pinochle/card_images/` over HTTP (UI-16) — a mount or a
  route backed by `CardImagePort`, with tests.
- **Gap 2:** the Node build stage in `docker/Dockerfile` (D3):

  ```dockerfile
  FROM node:22-slim AS frontend
  WORKDIR /build
  COPY frontend/package.json frontend/tsconfig.json ./
  COPY frontend/src ./src
  RUN npx -y typescript@5 tsc
  # …then in the runtime stage:
  COPY frontend/public ./frontend/public
  COPY --from=frontend /build/dist ./frontend/dist
  ```

**Check:** `/` and `/admin` return pages instead of the "not been built yet"
404, in both run modes; a card face and a card back each load by URL; opening a
join URL streams frames into the log.

#### A2 · Admin console

`admin.html` over the existing admin router: create a game with four named
seats (human or computer), start it, display the join links, abandon it.
Admin token entered once and held for the page session.

**Check:** create and run an all-computer game entirely from the browser, and
watch the whole game scroll past in A1's raw log.

#### A3 · Debug action panel

One plain form per player action, driven by the seat token of the tab: draw,
bid amount, pass, name trump, select four cards to pass, begin play, toss in,
play a card. Deliberately unstyled. Rejections (NFR-4) are printed verbatim.

**Check — the Phase A milestone:** a human seat plays a **complete game**
against three computers through raw forms, including a going-set round. The
HTTP action surface, token auth and event privacy are now proven before any
visual work exists. Bump to 0.4.0.

### Phase B — the client state model

#### B1 · Headless reducer

A pure `applyEvent(state, frame) → state` in `frontend/src`, no DOM, covering
all 22 event types plus the turn header, with `node --test` coverage.

Because RT-5 forbids a snapshot, this reducer *is* the client's only model of
the game: seats and teams, own hand, counts of others' hands, bid history,
contract and trump, exposed meld, current trick, last completed trick
(UI-14b), cumulative score, phase and pause state. It must never derive card
points taken during a round (UI-14c).

**Check:** code review in isolation, diffed against §4. A recorded event log
from an A2 game replays through the reducer to a correct final state.

### Phase C — presentation, one region at a time

Each slice renders from B1's state and deletes the debug controls it
supersedes.

| Slice | Contents | Requirements | Manual check |
|---|---|---|---|
| **C1** | Green felt table; four seats in true clockwise relation from the viewer's own seat; names; partnerships visually distinct; own hand face-up, fanned, sorted; other hands as fanned backs with correct counts; turn indicator; persistent scoreboard. Scale-to-viewport (D4). Render only — nothing clickable | UI-1…7, UI-14, UI-17 | Four windows tiled 2×2 on an all-computer game; everything updates; verified in both Chrome and Firefox. Bump to 0.5.0 |
| **C2** | Trick area: each card positioned nearer the player who played it; the server-owned trick-clear pause; last completed trick viewable on demand during the following trick | UI-6, UI-14b, UI-15, RT-8…11 | Watch a full round; confirm all four windows change phase together and no client runs ahead |
| **C3** | Card input: click a card to play it, and drag as the primary affordance; legal cards visually distinguished; illegal plays refused client-side and still rejected server-side | UI-8, UI-9, ARC-2 | Play out a trick phase from a real hand; confirm an illegal card cannot be submitted |
| **C4** | Bidding panel — entry constrained to multiples of 10 at or above the minimum, pass, running bid history — and the trump picker | UI-10, UI-11, UI-14a | Win an auction and name trump from the real UI |
| **C5** | Passing: select exactly four cards and confirm, using the same click-or-drag gestures; received cards shown to the receiving team only | UI-12, RT-1, NFR-6 | Pass to your partner; confirm the opposing seats' windows never show the cards |
| **C6** | Exposed meld face-up per player with per-player and per-team totals; team meld total retained for the round after the table clears; round summary with trick points; game-over screen | UI-13, UI-14a, UI-14c, FR-66 | Play a round to a score and a game to its winning score |
| **C7** | Remove the debug panel; confirm the Docker image serves the finished client; cross-browser pass; documentation | — | Full game played inside the container in both browsers. Bump to 1.0.0 |

---

## 6. Deferred and out of scope

- **Seat-lost and abandoned handling in the client is out of scope for this
  plan.** The server already publishes `seat_lost`, `seat_rejoined` and
  `game_abandoned`; the reducer ignores them beyond logging, and no banner or
  recovery UI is built. RT-12's requirement that the remaining players be told
  a seat is gone is therefore **not met by this plan** and is left to a later
  release.
- **Reconnection** — already out of scope by RT-5. A client that loses its
  stream cannot rebuild its view.
- **TLS, reverse proxy, public DNS, VPS deployment.** The VPS sections of
  `docs/docker-usage.md` are written but unverified, and should be marked as
  such until there is a host to verify them on.
- **Multiple concurrent games** (NFR-5), **durable storage** (NFR-8),
  **selectable difficulty** (FR-75), **tablet and phone layouts** (UI-17).

## 7. What cannot be verified on one desktop

| Concern | Substitute |
|---|---|
| Real network latency, and RT-11 lockstep under it | Chrome DevTools throttling, or `sudo tc qdisc add dev lo root netem delay 120ms` against bare `uvicorn` — inside Docker this needs `NET_ADMIN`, so run it outside the container. Do this once, at C2 |
| Four genuinely separate client machines | `uvicorn --host 0.0.0.0` and the desktop's LAN address lets a phone or second laptop take a seat. Not required by UI-17, but a free check that nothing depends on same-origin luck |
| TLS termination and proxy buffering of SSE | Cannot be tested locally in a meaningful way; deferred with the rest of deployment |
