# Change log for pinochle
All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning].
The format is based on [Keep a Changelog].

## [Unreleased]

### Added
- A seat whose player has gone can be given to the computer, and the game goes
  on from the point it stopped (RT-12a). The console offers two controls per
  human seat: **Unlink**, which revokes that player's credential and ends the
  streams opened with it, and **Seat computer**, which does the same and then
  hands the seat to the computer. The seat is replaced rather than re-created
  — same id, same place at the table, same cards — so a round in progress
  carries on, and if the seat was the one on the clock its move follows a
  moment later. A new `seat_replaced` frame tells the table which seat changed
  hands, and the client marks it computer-played from then on (UI-3)
- Seating a computer in the last human seat releases any hold that was waiting
  to be read, since there is no longer anybody to read it (RT-13)
- The round that ends the game is now summarised and held like any other
  before the winner is announced (FR-66, FR-71): the table reads whether the
  auction winner made the contract, and a Continue click brings up the result.
  An all-computer table has nobody to read it, so it goes straight through as
  before
- A **Play** button on the contract panel, to the left of **Toss in**, so the
  auction winner can begin play from the panel that offers them the choice.
  It does exactly what the notice area's Continue does — the exposed meld is
  held while it is read (RT-13), and releasing that hold is how play begins
  (FR-50a)

## [1.0.0] - 2026-09-21

First full release.

### Changed
- The Docker deployment reads its whole configuration from `.env` at the
  repository root rather than from settings baked into `docker/compose.yaml`,
  so a deployment is configured by editing one file. The published port and
  its host binding are now `PINOCHLE_BIND_ADDRESS` and `PINOCHLE_PORT`,
  defaulting to loopback on 8000, and the `make docker` targets run compose
  from the repository root with that env file
- The meld cards on the table are drawn larger, so a face-up meld can be read
  at a glance

## [1.0.0-RC1] - 2026-09-21

First release candidate.

### Added
- The meld is laid out face-up on the table rather than only named in a list.
  `meld_exposed` now carries the physical cards — both the whole face-up
  layout and, per combination, the cards arranged together for it — so the
  front end can group them as they would sit on a real table (FR-44, FR-45,
  UI-13). A card that supports several combinations at once, such as the queen
  of spades in both queens around and a pinochle, is laid down only once;
  duplicates are kept only where a double combination genuinely needs both
  physical copies
- A hold on the exposed meld (`MELD_EXPOSED`), so the table stops to be read
  before the opening lead. It is taken only when the table has a human seat,
  and releasing it is what begins play; an all-computer table runs straight
  through as before. `begin_play` refuses while the hold stands, and a toss-in
  clears it

### Changed
- The dealt packets fly along a bowed path from dealer to recipient rather
  than as two straight runs through the centre of the table, using a
  quadratic `offset-path` whose bow grows with the distance
- The deal runs at 150ms a packet — about two and a half seconds for the
  whole deal, down from five

## [0.5.0] - 2026-09-21

### Added
- The deal is now dealt rather than simply appearing: packets of three go
  round the table clockwise from the dealer's left, and the frames that
  arrive while it runs are held and applied once the presentation is over,
  so the animation is never interactive and never contradicts the server
- Each player's latest auction call sits beside their hand while the
  auction is live — the number bid or `pass` — and comes down as soon as
  the contract is settled
- A plaque in the lower left naming the winner of the auction and the
  amount, and a trump indicator in the lower right carrying the suit and
  its symbol, both of which stand for as long as the round does (UI-14)
- The administrator's console is served with the server's own table
  settings already in its form — the partnership names, the seat names and
  each seat's type. The admin token is filled in only when the URL already
  carries the valid one; the rest are configuration, not credentials

### Changed
- The notice band moved out of the stacked bottom bar and up to the top of
  the table, where it no longer competes with the hand for the space above
  it (UI-19, UI-19a)
- The other three hands are drawn as cards rather than as counters: three
  quarters of this seat's own face size, written as a ratio of it. A fan is
  now stated as the strip of each card that shows rather than as a fraction
  of the card, so tripling the card does not triple the fan's reach, and the
  same amount of edge still says how much of a hand is left (UI-5)
- Nothing in the hand changes places any more. A card under the pointer, or
  picked out for the pass, no longer jumps its neighbours to the top of the
  fan nor lifts out of it; being pointed at or chosen is said in colour
  alone — a thicker ring, a brighter face, and a gold ring with a glow for
  a chosen card — which stays legible on the strip down each card's left
  edge, the only part a click could ever reach (FR-17)
- The announcements from before the cards are led now end at the first card
  played. The dealer is on the seat's own label (UI-3) and the contract and
  trump are on the scoreboard (UI-14), so the band says nothing at all
  between the opening lead and the first trick taken

### Fixed
- The table could be drawn with its bottom edge below the window, putting
  the round summary's Continue button somewhere no click could reach.
  `#stage` now scales from its corner and takes the slack out of its layout
  box, so the box the body centres is the size the table is actually drawn
  at; checked from 1600x1250 down to 800x600. The harness now names an
  off-window control as blocked rather than reading it as undrawn
- An empty notice pill showed above the status line on a table with nothing
  to say yet, because `#notice` outranked the user agent's own
  `[hidden] { display: none }`
- The round-summary hold arrives one frame ahead of the summary itself, and
  for that frame the band held a Continue button and no headline; it now
  says the round is over until the summary lands

## [0.4.0] - 2026-09-21

### Added
- `docs/impl.md`: the sliced implementation plan for the remaining work (the
  front end), with a review point and a manual check per slice, the decisions
  locked before coding starts, and the single-desktop verification workflow
- `Makefile`, `scripts/dev.sh`, `scripts/seed.py`: the development loop
  (impl.md slice A0). `make dev` runs the server on localhost with a fixed
  admin token; `make seed` creates a game, prints the join links, and starts it
  once the human seats have opened their streams (FR-10b); `make seed-watch`
  runs an all-computer table
- `frontend/`: the browser client's own tree — TypeScript compiled by `tsc` to
  ES modules the browser loads directly, with no bundler and no runtime
  dependency (ARC-8). Phase A's page is a raw event log: the wire contract is
  reviewable before any presentation code exists. The seat token is held in the
  URL and `sessionStorage`, never `localStorage`, so four seats can be four
  tabs of one browser
- The administrator's console (impl.md slice A2): create a game with four
  named seats, copy each human seat's join link, see which seats have joined,
  start the game, abandon it, and watch the public event stream live. An
  all-computer table issues no join links, so the console's stream view is the
  only way to watch one
- The table itself (impl.md slices C1-C6): a green felt surface with the
  viewing player's seat at the bottom, the partner across and the opponents to
  either side (UI-1, UI-2); the partnerships distinguished and the acting seat
  marked (UI-3, UI-7); this seat's hand face-up and fanned in the order of
  FR-23, the other three as fans of backs at their true size (UI-4, UI-5); the
  trick with each card nearer the seat that played it (UI-6); the last
  completed trick on demand (UI-14b); a persistent scoreboard carrying the
  contract, the auction winner, trump, the bid history and each team's meld
  total for the whole round (UI-14, UI-14a); exposed meld per seat and per team
  (UI-13); the round summary and the game-over panel (FR-66, FR-71)
- Card input by drag or by click, the two being exactly equivalent (UI-8).
  Legal cards are distinguished from illegal ones and an illegal one cannot be
  submitted (UI-9) — legality is whatever the server's turn prompt listed, and
  no rule is decided in the browser (ARC-2)
- Controls for every phase a seat acts in: bid entry constrained to multiples of
  ten at or above the minimum, or pass (UI-10); accept or decline a lone
  bidder's contract (FR-32); the trump picker (UI-11); choose exactly four cards
  and confirm the pass, with the received cards shown to the receiving team only
  (UI-12); play the contract out or toss it in (FR-50a, FR-50b)
- The face-down dealer-selection spread, drawn from by clicking a position
  (FR-11, FR-11a)
- `frontend/src/state.ts`: the client's whole model of the game (impl.md slice
  B1). RT-5 puts no snapshot on the server, so this reducer is not a cache of
  something authoritative elsewhere — it is the only model the browser has.
  Pure `applyEvent(state, frame)`, no DOM, 47 tests under `node --test`
- `frontend/src/cards.ts`: card codes, and the hand order of FR-23/FR-23a —
  grouped by suit, descending by rank with the ten above the king, trump moving
  leftmost once it is named
- `scripts/record_frames.py` and `make record`: record one seat's event stream
  from an all-computer game as the reducer's test fixture, through the real
  service and the real encoder so it cannot drift from the wire format
- `make test` now runs the client tests as well as the server's, with
  `make test-py` and `make test-fe` for one at a time
- `pinochle/web/routers/cards.py`: card artwork over HTTP (UI-16), addressed by
  the same two-character wire code the event stream uses — `/cards/faces/TS`
  for the ten of spades, `/cards/backs/blue` for a back, either in SVG or PNG,
  cached immutably. Previously `CardImagePort` could resolve artwork on disk but
  nothing served it
- `CardImagePort` in the container's object graph, wired to `SvgCardImage`
- `PINOCHLE_CARD_BACK`: which back the hands are dealt with, read from a `.env`
  file in the repository root (see `.env.example`) or from the environment. The
  setting is a plain file name from `pinochle/card_images/backs/` — `castle`,
  or `castle.svg` — never a path; the server turns it into one. The client asks
  `/cards/back` for whatever that is, so no file name is spelled in the browser

- The notice area (UI-19): the table says in one sentence what just concluded —
  who won the draw, who won the auction, what trump is, who took the trick, how
  the round scored — the same words on all four screens. The server sends no
  prose: every fact a notice states already crossed the wire as an event, so
  `frontend/src/notice.ts` derives the sentence from the state the reducer
  already holds. There is no scrolling history; what deserves to outlive its
  moment is on the scoreboard (UI-14a), and the rest passes as it does at a
  physical table
- Holds (RT-13): a pause is now a named state the game occupies, carried on the
  turn header of every frame and delimited by `HoldBegun`/`HoldEnded`, ending
  either after an interval or when a player releases it. The round summary takes
  a released hold — the next deal waits on a seat rather than on a clock, because
  the summary has arithmetic in it that players read and argue about. Any one
  seat releases it, by voice-coordinated agreement rather than four clicks:
  `POST /api/games/{id}/acknowledge` names the hold it releases, so a late click
  releases nothing and two simultaneous releases emit one `HoldEnded`. A table
  of all computers takes no such hold, since there is nobody to read the summary
  and nobody who could end the wait
- `PINOCHLE_TEAM_NS`, `PINOCHLE_TEAM_EW` and `PINOCHLE_SEAT_<SEAT>_NAME`/`_TYPE`:
  the table the console's setup form is born holding, so a household that plays
  the same four seats every week stops retyping them. Per field rather than all
  or nothing — a key the file does not set keeps its built-in default — and a
  `_TYPE` that is neither `human` nor `computer` is refused at startup. These are
  only defaults; the form is still editable. `GET /api/admin/defaults` serves
  them behind the admin token, since the names on a configured table are the
  operator's own household
- `.env.example` now documents every variable the server reads rather than only
  the card back; ten of them were live and undiscoverable. Each is commented out
  beside its default, and tests fail if a setting has no line there or if any
  line is left uncommented
- Startup logs which `.env` file the settings were read from, if any, so an
  operator wondering why a setting didn't take can see whether the file was
  found at all
- `make test-browser`: `scripts/hit_test.py` replays the recorded seat stream
  through the real reducer, the real renderer and the real stylesheet in
  headless Chrome at three window sizes, and after every frame asks the browser
  what a click aimed at each control would actually hit. The controls are taken
  from where the click handlers are attached, so the list cannot drift from the
  code. Not part of `make test`, which should need nothing but
  `pip install -e .` and node
- **UI-18**: a visible control has to be clickable — stated as a requirement
  rather than living only in the harness that checks it, and scoped to the drop
  targets and to every window size the layout supports
- `python-dotenv` is now a dependency in its own right rather than arriving with
  `uvicorn[standard]`

### Changed
- `README.md` now says what the project is and how to run it, and
  `docs/docker-usage.md` describes the two-stage image it actually builds. The
  VPS half of that guide is marked unverified: the image and container are
  tested, a public host is not
- `docker/Dockerfile` is now a two-stage build: a Node stage compiles
  `frontend/src`, and the Python runtime image copies the result. The client is
  compiled in the image rather than copied from the host, so the image can never
  serve a stale `frontend/dist`
- A missing front-end page now names the file and suggests `make build`, rather
  than reporting that the front end does not exist
- FR-75a now states that a computer player's bid valuation is a *partnership*
  valuation — its own meld, the trick points both hands together can take, and
  an allowance for the partner's contribution — rather than a valuation of its
  own hand alone, which no hand could ever bid on

- The dealer-selection spread is now thrown across the felt (FR-11c): 48 cards
  strewn over the inner two thirds of the table, each turned a little and lying
  across the others, rather than three rows of a 16-column grid. Overlap is the
  point, so a card can be dragged aside to reach what is under it and stays
  where it is put; a press that travels more than four pixels moves the card and
  a press that stays put draws it, so a click that wobbles still draws. A drawn
  card leaves the table and is shown face up in front of its drawer's seat
  (FR-11d). Where each card lies is settled once per spread, not once per frame
- FR-23 laid a hand out spades, hearts, diamonds, clubs, which puts the two red
  suits next to each other — and a fan shows only each card's corner index, so
  that boundary had to be read off the pips rather than noticed. The order is
  now spades, hearts, clubs, diamonds, and under FR-23a the three non-trump
  suits follow trump in alternating colour: SHCD, HSDC, CHSD, DSHC
- The hand is held as a hand (UI-4): each card turned a little further about a
  pivot below the fan, so the cards sweep an arc and lie across one another with
  only the corner rank and suit showing. Spacing falls out of the tilt and the
  pivot rather than being set anywhere, so a hand closes up as it is played out
- The card art is twice the size it was (UI-4, UI-6, UI-12, UI-13, UI-14b), and
  the stage grew from 1180x830 to 1420x1000 to make room for it. UI-17's
  scale-to-fit still applies, so a narrow window gets less than a literal 2x in
  exchange for a table that does not overlap itself. Card backs keep their
  original size: there is nothing on a back to read
- The meld is now a section of the scoreboard rather than a panel of its own
  across the middle of the table, where the trick goes. The named combinations
  show only while the meld is on the table and give way to the totals once the
  first trick is gathered (UI-14a), and the scoreboard closes to its own heading
- The passed-cards display (UI-12) comes down when the auction winner is on turn
  to lead rather than when the first card is played: by then the pass has been
  read and what the table needs is the room to play in

### Security
- The administrator's SSE endpoint now accepts its token as `?t=` as well as in
  the `X-Admin-Token` header, because `EventSource` cannot set headers. It sits
  on a router of its own so that only this read-only route accepts a token that
  way: every command that changes a game still requires the header, so a
  forwarded URL cannot create, start or abandon a game

### Fixed
- The console answered "Bad admin token." with no way to tell what token it
  wanted. It now accepts the token from the URL — `/admin?t=<token>`, which
  `make dev` prints ready to open — asks for the credential before anything
  else on the form rather than after the seats, and when the token is refused
  says where an operator is supposed to find one. Refused credentials are also
  logged now, with the path and the reason but never the token itself, which
  NFR-9 asked for and only this omission was missing
- The client offered a card during the trick-clear pause, which the server
  rejects as out-of-phase (RT-9): a pause is a state the game occupies, not a
  presentation effect, so no play is offered while one runs
- A seeded game was not reproducible (NFR-7). The computers' dealer-selection
  draw used the unseeded global `random`, and the driver scheduled the waiting
  seats straight from a `set`, whose iteration order depends on string hashing
  and differs between processes. The draw picks the dealer and the dealer
  decides which twelve cards of the shuffle each seat receives, so a seeded
  shuffle alone reproduced nothing. `ComputerPlayerStrategy` now takes the
  game's own `Random`, and the driver walks the waiting seats by seat position
- A request for artwork that is well-formed but absent from disk is now a 404
  rather than an unhandled `FileNotFoundError` and a 500
- The computer player now bids. It valued a hand as its own meld plus a trick
  estimate from its own twelve cards, but a contract is scored against the
  partnership, so the valuation could not reach the 250 minimum (FR-27) and the
  strategy passed unconditionally: an all-computer game abandoned 302 of 309
  rounds under FR-31 and took 212 rounds to finish. `choose_bid` now adds
  `_PARTNER_CONTRIBUTION`, a flat allowance of 180 for what the partner brings,
  which over 16 complete games cuts a game to 13.4 rounds, with a tenth of them
  abandoned and the bidding side making its contract 64% of the time. The
  allowance is a single figure meant to be tuned by playing games
- Clicking Play or Toss in at the meld did nothing at all: no move, no error, no
  request. The trick layer is a fixed 300x260 box whether or not a card has been
  played, and during the meld `#centre` grows tall enough to put that invisible
  box 113px into the bottom bar — exactly over the row of buttons — while
  carrying a `z-index` the bar did not answer. A seat's own cards and controls
  now sit over the felt's contents. Not fixed with `pointer-events: none`, which
  would break the trick's other job as the drop target for playing a card (UI-8).
  The same fault was silently eating drops on the pass tray
- Passing two copies of the same card looked as though only one could be chosen.
  The selection was never the problem — it is held by position in the hand — but
  `hand.ts` set the fan's order as an inline `z-index`, which outranks the
  stylesheet, so the rule that lifts the hovered or chosen card never applied and
  a chosen card stayed buried under its twin. The fan's order now goes into a
  `--stack` custom property and the stylesheet does the stacking
- A client that lost its SSE stream showed a table that looked perfectly normal
  but was frozen at the last frame it heard, and its Play button still sent a
  move the player would never see the result of. A seat that loses its stream
  can now get back to the table (RT-5a)
- A draw arriving after the dealer was settled came back as a 500 with a
  `KeyError` behind it — from a tab still showing the spread, or one that had
  just reconnected to a round already under way. The spread's absence is the
  phase check for drawing, so it is now a `WrongPhaseError` and a 409 the client
  can display
- The turn prompt went on offering stale controls for a phase the table had
  already left, because it was only ever replaced by the next `turn_prompt`
  addressed to that seat and the server does not send one for every phase change
  (NFR-4). A prompt is now good only while the turn header still agrees with it

## [0.3.0] - 2026-09-07

### Added
- `pinochle/domain/errors.py`: the `PinochleError` hierarchy
  (`UnknownGameError`, `NotYourTurnError`, `WrongPhaseError`,
  `IllegalActionError`, `SetupError`), replacing bare `ValueError`/`KeyError`
  across the domain and service layers
- `pinochle/adapters/`: `AsyncioScheduler` and `FakeScheduler` (a
  virtual-clock `SchedulerPort`, so tests never wait in real time for a
  pause to elapse), `InMemorySeatTokens`, `SseNotification`,
  `LoggingNotification`, `CompositeNotification`
- `pinochle/ports/seat_token_port.py`: `SeatTokenPort`, the per-seat
  credential a join link carries
- `pinochle/web/`: a full FastAPI + Server-Sent Events layer — admin,
  player, and stream routers; seat and admin token authentication; a
  `PinochleError`-to-HTTP-status mapping; the `card_codec`/`event_encoder`/
  `turn_header` wire format; a `TurnPrompt` event, so a client is told what
  is legal rather than deriving it
- `pinochle/services/computer_driver.py`: `ComputerDriver`, driving every
  computer seat through the same ports a human client uses;
  `pinochle/services/seat_view.py`: `SeatView`, the private slice of state a
  strategy is allowed to see
- Bidding (`choose_bid`) and passing heuristics in `ComputerPlayerStrategy`,
  replacing the placeholder that always passed the four lowest cards
- `docker/Dockerfile`, `docker/compose.yaml`, `.dockerignore`: a
  backend-only container image — the browser front end is a later addition
- Seedable shuffling end to end (`Deck.shuffle`, `Round.deal`,
  `GameService`'s `rng` parameter)
- 277 unit and integration tests, including an all-computer game driven to
  `game_over` with no browser, over both a bare service and the full
  production container

### Changed
- `BidPlaced` now carries `current_high`; `TrickCompleted` carries
  `(player_id, card)` pairs instead of bare cards, so the wire format never
  has to re-derive who played what
- `GameService` takes `trick_clear_seconds` and `rng` as constructor
  arguments instead of a module constant and the global `random` module
- Moved `pytest-asyncio`, `fastapi`, `uvicorn[standard]`, and `httpx` into
  `[project.dependencies]`

### Fixed
- The `pinochle` logger tree was never configured, so the action/event
  audit log never reached `docker compose logs`; a generated admin token
  was never logged either — both now happen at startup

## [0.2.0] - 2026-09-06

### Added
- Hexagonal (ports and adapters) architecture
- `pinochle/domain/`: pure game logic — `Rank`, `Suit`, `Card`, `Deck`,
  `Player`, `Team`, `Hand`, `BiddingRound`, `detect_meld`, `Trick`,
  `scoring`, `Game` aggregate root with domain events
- `pinochle/ports/`: `AdminPort`, `PlayerActionPort` (inbound);
  `GameStatePort`, `NotificationPort`, `CardImagePort` (outbound)
- `pinochle/adapters/`: `InMemoryGameState`, `PrintNotification`,
  `SvgCardImage`
- `pinochle/services/`: `GameService` use-case layer and the `Round`
  state machine that orchestrates a single round
- `pinochle/strategies/`: `ComputerPlayerStrategy` (rule-based AI)
- `pinochle/app.py`: `create_default_app()` wiring entry point
- Full domain event stream, so a client can render the table from the
  events alone: `GameConfigured`, `DealerSelectionStarted`, `DrawMade`,
  `DrawTied`, `RoundStarted`, `ContractOffered`, `PlayBegun`,
  `SeatThinking`, `CardPlayed`, `TrickCleared`
- `TeamRoundScore`, carrying a team's whole round arithmetic (meld, card
  points, last-trick bonus, round total, points applied, cumulative)
  rather than a single figure
- `docs/requirements.md`: the settled specification, with §10 as the
  decision record
- `docs/design.md`: how the requirements will be built
- `docs/docker-usage.md`: Docker and VPS deployment guide
- Detailed docstrings across every class and module
- `pyproject.toml`: package metadata and pytest configuration
- 170 unit tests across `tests/domain/`, `tests/ports/`,
  `tests/adapters/`, `tests/services/` and `tests/strategies/`

### Changed
- Dealer selection draws from one shared face-down spread, replaced
  wholesale on a tie, instead of per-player draws
- The auction winner ends the meld display, or tosses the contract in
- The server is the sole owner of all game timers
- Renamed the `cards` package to `card_images` and cleaned up its layout
- Simplified the ports and adapters directory structure
- Moved pytest and pytest-mock into `[project.dependencies]`, so
  `pip install -e .` alone is enough

### Fixed
- Meld marriages, dealer rotation, and team derivation
- Turn-order enforcement and the must-beat rule
- Meld capture, the meld hold, and event privacy

### Removed
- Seat substitution, deferred past the first release
- Reconnection, deferred past the first release
- The computer strategy, deferred past the first release
- The unused `players` package
- Superseded design documents

## [0.1.0] - 2026-03-27
Beginning of ports and adapters version

## [0.0.0] - 2023-07-19
Start of Go version

[Semantic Versioning]: http://semver.org
[Keep a Changelog]: http://keepachangelog.com
[Unreleased]: https://github.com/philhanna/pinochle/compare/1.0.0..HEAD
[1.0.0]: https://github.com/philhanna/pinochle/compare/1.0.0-RC1..1.0.0
[1.0.0-RC1]: https://github.com/philhanna/pinochle/compare/0.5.0..1.0.0-RC1
[0.5.0]: https://github.com/philhanna/pinochle/compare/0.4.0..0.5.0
[0.4.0]: https://github.com/philhanna/pinochle/compare/0.3.0..0.4.0
[0.3.0]: https://github.com/philhanna/pinochle/compare/0.2.0..0.3.0
[0.2.0]: https://github.com/philhanna/pinochle/compare/0.1.0..0.2.0
[0.1.0]: https://github.com/philhanna/pinochle/compare/0.0.0..0.1.0
[0.0.0]: https://github.com/philhanna/pinochle/compare/b4aba0b..0.0.0
