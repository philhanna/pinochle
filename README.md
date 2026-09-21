# pinochle

A four-player Pinochle game for the web: a Python server that owns every rule,
and a browser client per player that renders the table from that player's seat.

Rules: [Pinochle on Wikipedia](https://en.wikipedia.org/wiki/Pinochle).
Repository: [github.com/philhanna/pinochle](https://github.com/philhanna/pinochle).

## Running it

```sh
pip install -e .          # everything, tests included
make dev                  # server on http://localhost:8000, admin token "dev"
```

`make dev` prints a console link with the admin token already in it — open
that, create a game, and open each human seat's join link in **its own tab**:

```
console:        http://localhost:8000/admin?t=dev
```

Without the token in the URL the console asks for it, and it is whatever
`PINOCHLE_ADMIN_TOKEN` was set to (`make dev` uses `dev`), or the value the
server logs at startup if it was not set.

Then:

```sh
make seed                 # or: create a game from the command line instead
make seed-watch           # four computer players, nothing to join
make test                 # server and client tests
make test-browser         # plus: is every control actually clickable?
make docker               # the same thing as a container image
```

A seat's join link is the only copy of its token, and a seat cannot rejoin
once its stream closes, so keep the link until the game is over.

Settings go in a `.env` file in this directory — copy `.env.example` — or in
the environment, which wins over the file. `PINOCHLE_CARD_BACK` chooses the
card back by the plain file name of an image in `pinochle/card_images/backs/`
(`castle`, `frog`, `red2`, …); `docs/docker-usage.md` lists the rest.

## How it is put together

Ports and adapters, with the server as the sole authority on state and rules:

- `pinochle/domain/` — cards, meld, tricks, scoring. No web, no storage.
- `pinochle/ports/` and `pinochle/adapters/` — one abstract base class per
  port; in-memory state, SSE notification, an asyncio scheduler, card artwork.
- `pinochle/services/` — the use cases, and the driver that plays the computer
  seats through the same ports a human client uses.
- `pinochle/web/` — FastAPI. Actions are ordinary HTTP requests; state changes
  are pushed over Server-Sent Events, one stream per seat.
- `frontend/` — TypeScript compiled by `tsc` to ES modules the browser loads
  directly. No bundler and no runtime dependency.

## Documents

- `docs/requirements.md` — what the system must do. Authoritative.
- `docs/impl.md` — how it was built, slice by slice, and how each was checked.
- `docs/docker-usage.md` — running it in a container, and deploying it.
- `CHANGELOG.md` — what changed, and why.
