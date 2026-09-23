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

A stream opens with one frame the domain knows nothing about,
`stream_started`, built by the stream router itself: it carries this seat's
position, player id, name, and a `partial` flag saying whether it joined a
round already in progress. It is how a client learns which seat it is.

Then the game event types, in the order a round produces them:

| Phase | Events |
|---|---|
| Setup | `game_configured`, `seat_replaced` |
| Dealer selection | `dealer_selection_started`, `draw_made`, `draw_tied`, `dealer_selected` |
| Deal | `round_started`, `cards_dealt` *(private, NFR-6)* |
| Bidding | `bid_placed`, `contract_offered`, `round_abandoned` |
| Trump & pass | `trump_named`, `cards_passed` *(team-private)* |
| Meld | `meld_exposed` |
| Play | `play_begun`, `contract_tossed_in`, `seat_thinking`, `card_played`, `trick_completed`, `trick_cleared`, `turn_prompt` |
| Pause | `hold_begun`, `hold_ended` |
| End | `round_scored`, `game_over` |

`seat_replaced` amends the table rather than opening it: a computer has taken
a seat over from a player who left (RT-12a), and the client folds it over the
seat it already has.

Three further types — `seat_lost`, `seat_rejoined`, `game_abandoned` — are
also published by the transport rather than the domain. **The client does not
handle them in this plan** (§6). With `stream_started`, that makes 29 names in
all; `EventSource` has no wildcard listener and every frame is named on its
`event:` line, so a client must subscribe to each name individually and a name
it omits is a frame it silently never receives.

**`seq` is monotonic but not contiguous on a player's stream.** Numbers are
assigned per game, and the frames addressed to other seats consume them, so a
seat sees gaps — a deal shows as `round_started` at 14 and this seat's
`cards_dealt` at 17, the missing 15, 16 and 18 being the other three hands
(RT-1, NFR-6). The reducer must treat a gap as normal and never wait for a
missing number.

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
- `Makefile` — `make dev`, `make seed`, `make seed-watch` (four computers),
  `make test`, `make docker`, `make build`, `make watch`.

  The pauses are server settings, not per-game ones, so watching a game at
  full speed means starting the server with `make dev-fast`
  (`PINOCHLE_COMPUTER_DELAY_SECONDS=0`, `PINOCHLE_TRICK_CLEAR_SECONDS=0`) and
  then seeding into it.

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
  RUN npx -y -p typescript@5 tsc
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
  release. The *recovery* half of it is built: the console can unlink a player
  and seat a computer in their place, and the table is told which seat changed
  hands (RT-12a).
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

## 8. Progress

### Done

- **A0** — `Makefile`, `scripts/dev.sh`, `scripts/seed.py`.
- **A1** — `frontend/` (TypeScript, ES modules, no bundler), the raw-frame log
  page, the card-artwork routes, and the Dockerfile's Node stage.
- **A2** — the administrator's console: create a game with four named seats,
  hand out the join links, watch who has joined, start, abandon, and a live
  view of the public event stream.

  One server change was needed for it. The administrator's SSE endpoint
  required the `X-Admin-Token` header, which `EventSource` cannot set, and an
  all-computer table issues no join links — so there was no way to watch one in
  a browser at all. That endpoint now also accepts its token as `?t=`, and lives
  on its own router so that only it does: every command still requires the
  header, and a forwarded URL cannot create, start or abandon a game.

Verified: a complete all-computer game ran on the host in about six seconds
with pauses at zero, and its 4,037 frames arrived in order on the admin
stream. Not one `cards_dealt` or `cards_passed` frame
appeared on that stream across all 309 deals, which is NFR-6 holding
structurally rather than by filtering. A human seat's stream carried its own
hand and nobody else's. The image builds, serves the compiled client, and runs
a game; `make test` is green at 318 server tests and 79 client tests.

- **B1** — the client state model, headless: `frontend/src/state.ts` (the
  reducer) and `frontend/src/cards.ts` (card codes and hand order), with 47
  tests run by `node --test` and no DOM anywhere.

  The replay fixture is recorded, not written: `scripts/record_frames.py`
  (`make record`) plays an all-computer game through the real service and keeps
  what one seat's stream carried, encoded by the real encoder, so it cannot
  drift from the wire format. It has the awkward properties of a real stream —
  201 frames whose sequence numbers skip 55 values where other seats' private
  frames fell.

  Two defects surfaced, both in code outside the reducer:

  * A count adjusted at one end of the pass but not the other. Found by a unit
    test, then pinned by a replay invariant: every seat holds twelve cards when
    play begins.
  * A seeded game was not reproducible (NFR-7). The computers' dealer-selection
    draw used the unseeded global `random`, and the driver scheduled the
    waiting seats straight from a `set`, whose iteration order depends on
    string hashing and so differs between processes. Since the draw picks the
    dealer, and the dealer decides which twelve cards of the shuffle each seat
    receives, a seeded shuffle alone reproduced nothing. Found by re-recording
    the fixture and getting a different game.

- **C1–C6** — the table: felt and seats (UI-1…7, 17), the trick area and the
  server-owned pause (UI-6, 15, RT-8…11), the last trick on demand (UI-14b),
  card input by click and by drag (UI-8, 9), the bidding, trump, passing and
  meld controls (UI-10…13), the scoreboard with retained bid history and meld
  totals (UI-14, 14a), the round summary and the game-over panel (FR-66, 71).

  They landed as one change rather than six because the modules interlock: the
  panels read the same prompt the hand does, and both draw from the same
  placement logic. The slices remain the right way to *review* it, and each is
  listed in §5 with its own manual check.

  **A3, the debug action panel, was skipped as superseded.** Its purpose was to
  prove the action surface before any presentation existed; the surface was
  proved instead by driving every endpoint over HTTP (A1 and A2's checks, and a
  scripted play-through of two complete rounds), so building a throwaway form
  per action and then deleting it in C7 would have been waste.

  Two requirements were only half met by the first pass and are now complete:
  UI-12's received cards were merged into the hand where nothing distinguished
  them, and FR-23a asks that the trump re-sort be *made visible* rather than
  instantaneous — the hand is rebuilt rather than moved, so there is nothing for
  a CSS transition to interpolate and the cards are pulsed into their new order
  instead.

- **C7** — the image carries the finished client (checked by fetching the
  compiled modules and the stylesheet out of a running container), the
  deployment guide no longer describes a Dockerfile that has since changed, and
  its VPS section is marked unverified because there is still no host to verify
  it on. There was no debug panel to remove, A3 having been skipped.

  What the code holds to, and where:

  * No rule is decided in the browser (ARC-2). Legality is whatever the turn
    prompt listed; `layout.ts` never inspects a card's rank or suit to decide
    whether it may be played.
  * No client timer affects what is displayed (RT-8). A pause is read from the
    turn header, and while one runs no card is offered — the server rejects a
    play during the trick-clear pause as out-of-phase (RT-9), so offering one
    would only earn a refusal.
  * The layout is one fixed size scaled to the window (UI-17), which is what
    lets four windows tiled on a single monitor each show a whole table. The
    factor is set from script because CSS cannot divide a length by a length.

### Fixed after a review point

- **The computer player almost never bid (FR-75a).** Watching an all-computer
  game showed every one of 1,236 bids was a pass: 302 of 309 rounds were
  abandoned under FR-31, and the only 7 played were forced contracts the dealer
  accepted at the 250 minimum.

  `choose_bid` valued a hand as its own meld plus a trick estimate from its own
  aces and length. But a contract is scored against the *partnership* — both
  partners' meld plus the card points the side takes — and measured over 4,000
  random deals a single hand's own valuation has a median of 60 and clears 250
  less than 1% of the time. The threshold was unreachable by construction, so
  the strategy passed unconditionally.

  Fixed by adding `_PARTNER_CONTRIBUTION`, a flat allowance for what the
  partner brings, and by amending FR-75a to state that the valuation is a
  partnership valuation. Measured over 16 complete games:

  | | rounds/game | abandoned | contract made | mean contract |
  |---|---|---|---|---|
  | before | 212.2 | 96.8% | 96.3% | 250.7 |
  | allowance 130 | 18.1 | 53.6% | 85.8% | 256.5 |
  | allowance 160 | 13.2 | 25.0% | 69.8% | 262.7 |
  | allowance 170 | 12.6 | 16.4% | 69.6% | 265.7 |
  | **allowance 180 (shipped)** | **13.4** | **9.8%** | **63.9%** | **270.9** |

  The allowance is a single tunable figure, not a model of the partner's hand,
  and the progression shows what it buys. A low allowance bids under the hand's
  worth: rounds are thrown in rather than played, and the side that does bid
  almost always makes it — 130's 85.8% is a symptom, not a strength. Up to 170
  that is pure gain, the made rate holding just under 70% while abandoned
  rounds fall from a half to a sixth. At 180 the trade has arrived: abandoned
  rounds reach a tenth, but the made rate drops to 64% and rounds per game
  stop falling, because rounds lost to a redeal are simply traded for rounds
  lost going set. 170 is the measured optimum on this formula; 180 buys fewer
  redeals with contracts.

  The better next lever is the formula rather than the figure: `_trick_estimate`
  counts only aces in the prospective trump suit, though an off-suit ace still
  takes a trick. A sweep counting them at 10 apiece reached 6.9% abandoned with
  69.8% made — better on both axes than any flat allowance tried here.


## 9. What a machine cannot check here

The table itself was never looked at while it was written: this environment has
no browser. Everything that could be tested without one was — the reducer, the
seat placement, the legality rule, every line of text the table puts on screen,
all replayed against a recorded game — and the rest was verified as far as HTTP
reaches: every asset the page loads returns 200 from both the dev server and the
image, and a script drove a human seat through two complete rounds by making
exactly the requests the table's controls make, in the order they make them.

What that leaves genuinely unchecked is the appearance and the gestures:

1. **Four windows, tiled 2×2** on one monitor, one seat each, plus the console
   in a fifth. Everything should be legible at quarter-screen; if it is not,
   the stage is one fixed size and `--stage-width`/`--stage-height` in
   `table.css` are the two numbers to change.
2. **The seating.** Your own seat at the bottom, your partner across, and the
   seat that plays after you on your left. That last one is an interpretation
   of UI-1's "true clockwise relationship" and is the thing most worth a second
   pair of eyes; `placement()` in `layout.ts` is the one place to change it,
   and `test/layout.test.js` says what it currently claims.
3. **Drag and drop**, which no test here exercises. Click is wired to the same
   call, so if a drag misbehaves the game is still playable.
4. **Chrome and Firefox both** (UI-17). The client uses no feature newer than
   ES2022 modules and `EventSource`, but that is an argument, not a test.
5. **The pace of it** — whether 1.5 seconds on a trick and one second on a
   computer's move feel right. Both are environment variables
   (`PINOCHLE_TRICK_CLEAR_SECONDS`, `PINOCHLE_COMPUTER_DELAY_SECONDS`), so this
   is tuning rather than editing.
