# Docker usage

This guide explains what Docker does for Pinochle and how to operate the
container without requiring prior Docker experience. For the underlying design
decisions, see [Docker in the system design](design.md#10-docker).

The image includes the Python server, compiled browser client, and card
artwork. The player table at `/` and administrator console at `/admin` are
served by the same container as the HTTP API and event streams.

## What Docker provides

Docker packages the application and everything needed to run it into an
**image**. Starting that image creates a **container**, which is an isolated
running instance of the application. Docker Compose reads
`docker/compose.yaml` and supplies the port mapping, configuration, and restart
policy. The image defines its own health check.

Pinochle uses one image and one container:

```text
Browser ── http://host:8000 ──> host port 8000
                                   │
                                   v
                         Pinochle container
                         ├─ FastAPI HTTP API
                         ├─ Server-Sent Events
                         └─ the compiled client and card artwork
```

There is no database container, Node container, or persistent data volume.
Game state lives in memory only (NFR-8), so restarting the container loses a
game in progress; there is nothing to back up and nothing to migrate.

## How the image is built

The image is built in two stages. A Node stage compiles `frontend/src/` with
`tsc`; the runtime stage installs the `pinochle` Python package and copies in
the compiled modules alongside `frontend/public/`. Node is not in the finished
image — only its output is.

The client is compiled inside the image rather than copied from the host, which
is why `.dockerignore` excludes `frontend/dist`: whatever is built locally
cannot leak into a release and make the image disagree with the source.

The server runs as an unprivileged user. Uvicorn listens on port 8000 inside the
container. Compose maps it to `127.0.0.1:8000` on the host by default, so the
game is not exposed to the internet without an explicit binding or proxy.

## Prerequisites

Install Docker Desktop on Windows or macOS, or Docker Engine with the Compose
plugin on Linux. Confirm that both Docker and Compose are available:

```console
docker --version
docker compose version
```

Run the commands below from the repository root.

## Configure the application

Copy the example configuration, then set a private admin token and the public
URL that players will use:

```console
cp .env.example .env
```

```dotenv
PINOCHLE_ADMIN_TOKEN=replace-this-with-a-long-random-secret
PINOCHLE_PUBLIC_BASE_URL=http://localhost:8000
```

Do not commit `.env`; it contains an administrator credential. For play from
other computers, replace `localhost` with the host's LAN name, LAN address, or
public HTTPS address. The public base URL is embedded in player join links, so
it must be reachable from the players' browsers.

If `PINOCHLE_ADMIN_TOKEN` is empty, the application generates one at startup
and writes it to the container log. Supplying it explicitly is less surprising
because the value remains the same when the container is recreated.

Compose passes every value in `.env` into the container, including team names
and seat defaults. The Python application uses its built-in defaults for
values omitted from the file. Keep `.env` on the server and set its permissions
to `600`; it is excluded from the image build context.

Other settings have usable defaults:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PINOCHLE_TRICK_CLEAR_SECONDS` | `1.5` | How long a completed trick remains visible |
| `PINOCHLE_COMPUTER_DELAY_SECONDS` | `1.0` | Delay before a computer player acts; `0` disables it |
| `PINOCHLE_LOG_LEVEL` | `INFO` | Application log verbosity |
| `PINOCHLE_SSE_KEEPALIVE_SECONDS` | `15` | Interval between stream keepalive frames |
| `PINOCHLE_SSE_QUEUE_MAXSIZE` | `256` | Maximum queued events for one browser connection |
| `PINOCHLE_CARD_BACK` | `blue` | Card back the hands are dealt with: the plain file name of an image in `pinochle/card_images/backs/`, such as `castle` or `castle.svg`. A path is refused at startup |
| `PINOCHLE_BIND_ADDRESS` | `127.0.0.1` | Host address Docker publishes; use `0.0.0.0` only for deliberate direct access |
| `PINOCHLE_PORT` | `8000` | Host port Docker publishes |

## Build and start

Build the image and start the container in the background:

```console
docker compose --env-file .env -f docker/compose.yaml up --build --detach
```

The first build takes longer because Docker must download base images and
install dependencies. Later builds reuse cached layers when their inputs have
not changed.

Check these addresses after the container starts:

- Health check: <http://localhost:8000/healthz> — should return `{"status":"ok"}`
- Player table: <http://localhost:8000/> and administrator console:
  <http://localhost:8000/admin>.

The host binding is `127.0.0.1:8000:8000`: host address, host port, container
port. Set `PINOCHLE_PORT=8080` in `.env` if host port 8000 is occupied, and
update `PINOCHLE_PUBLIC_BASE_URL` accordingly. To connect directly from other
computers, set `PINOCHLE_BIND_ADDRESS=0.0.0.0` and restrict access with a
firewall. A public deployment should use an HTTPS reverse proxy instead.

## Check status and logs

Show the container and its health status:

```console
docker compose --env-file .env -f docker/compose.yaml ps
```

Follow application logs until interrupted with Ctrl+C:

```console
docker compose --env-file .env -f docker/compose.yaml logs --follow pinochle
```

Stopping log output does not stop the container. The health check periodically
requests `/healthz`; a healthy response is `{"status":"ok"}`.

## Stop or restart

Stop and remove the container and its Compose network:

```console
docker compose --env-file .env -f docker/compose.yaml down
```

This leaves the built image in Docker's local cache. Start it again with the
`up` command. To restart the existing container without rebuilding it:

```console
docker compose --env-file .env -f docker/compose.yaml restart pinochle
```

Compose uses `restart: unless-stopped`, so Docker restarts the container after a
crash or host reboot unless an operator deliberately stopped it.

## Rebuild after a change

The source tree is copied into the image during the build. Editing a local file
does not change an already-running container. Rebuild and recreate it with:

```console
docker compose --env-file .env -f docker/compose.yaml up --build --detach
```

Use the logs command afterward if the new container does not become healthy.
A development-only Compose override may eventually bind-mount source and run
Uvicorn with `--reload`, but reloading disconnects every player and loses the
current game.

## Data lifetime and scaling constraints

All game state is held in memory. Consequently:

- restarting, replacing, or stopping the container loses every game in
  progress;
- no host directory or Docker volume contains a recoverable game;
- `docker compose down` and `docker compose restart` should be used only when
  interrupting active games is acceptable.

The deployment must use exactly one Uvicorn worker and one Pinochle container.
Do not add Compose replicas or increase the worker count: each process would
have an independent in-memory game and independent event streams.

## Transfer an image to another server

You can build on your development computer and copy the image without copying
the source tree. Use this only when both computers have the same CPU
architecture; otherwise build the image on the destination server.

On the development computer, from the repository root:

```console
docker build -f docker/Dockerfile -t pinochle:latest .
docker save -o /tmp/pinochle-image.tar pinochle:latest
scp /tmp/pinochle-image.tar operator@your-server:/home/operator/
```

On the server, put a private `.env` file in `/home/operator/`, then load and
run the image. Set `PINOCHLE_PUBLIC_BASE_URL` in that file to the address
players will actually use (normally an HTTPS domain):

```console
chmod 600 /home/operator/.env
docker load -i /home/operator/pinochle-image.tar
docker run -d --name pinochle --restart unless-stopped \
  --env-file /home/operator/.env \
  -p 127.0.0.1:8000:8000 pinochle:latest
curl http://127.0.0.1:8000/healthz
```

Use a reverse proxy on the server to publish HTTPS (below). If you want direct
LAN access instead, change the port mapping to `0.0.0.0:8000:8000` and apply
appropriate firewall rules. Keep the `.env` file separate from the image; it
contains the administrator credential and your table defaults.

For an update, stop and remove the old `pinochle` container before running the
new image. Do this between games: all game state is in memory and will be lost.
You may then remove the transferred tarball if you no longer need it.

## Hosting behind a reverse proxy

The browser receives game updates through a long-lived Server-Sent Events (SSE)
connection. A reverse proxy must pass that connection through without response
buffering and with a read timeout comfortably longer than the 15-second default
keepalive interval. The server sends `X-Accel-Buffering: no`, which nginx
understands, but the proxy still needs SSE-appropriate buffering and timeout
settings.

Use HTTPS for an internet-facing deployment. Keep the administrator token
secret, expose only the required HTTP port, and set
`PINOCHLE_PUBLIC_BASE_URL` to the externally reachable HTTPS URL.

## Deploy to a public VPS

> **Unverified.** Everything above this line has been run: the image builds, the
> container serves the game, and a full round has been played inside it. The
> steps below — a VPS, a domain, TLS through a reverse proxy — have not, because
> there is no host to run them on yet. Treat them as a plan to check rather than
> a procedure known to work, and expect the TLS and proxy details in particular
> to need adjusting. One thing worth knowing before you start: Server-Sent
> Events break if a proxy buffers responses, which is what the
> `X-Accel-Buffering: no` header and the Caddy configuration below are for.

Use this topology when the development computer is not reachable from the
internet:

```text
Developer computer ── source or image ──> Public VPS

Players ── HTTPS on port 443 ──> Caddy
                                      │
                                      └─ HTTP over 127.0.0.1:8000
                                                     │
                                                     └─ Pinochle container
                                                        (one Uvicorn worker)
```

The VPS, not the development computer, is the production host. Players connect
to a domain name that resolves to the VPS. The reverse proxy accepts public
HTTPS requests and forwards them to Pinochle through the VPS loopback
interface.

### 1. Prepare the VPS and DNS

Provision a Linux VPS, create a non-root operator account with SSH-key access,
install Docker Engine with the Compose plugin, and keep the operating system
updated. Follow Docker's installation instructions for the VPS distribution
rather than an unofficial convenience script.

Create a DNS `A` record that points the game hostname, such as
`pinochle.example.com`, to the VPS IPv4 address. Add an `AAAA` record only when
IPv6 is configured and reachable on the VPS. DNS may take time to propagate.

Configure both the VPS provider's network firewall and the host firewall to
allow:

- TCP 80 for HTTP redirects and certificate issuance;
- TCP 443 for the game over HTTPS;
- the SSH port, preferably restricted to trusted source addresses.

Do not allow public access to TCP 8000. Docker manages its own packet-filtering
rules, so the loopback-only port binding in the next step is important; relying
only on a host firewall can expose a published Docker port unexpectedly. See
[Docker's firewall documentation](https://docs.docker.com/engine/network/packet-filtering-firewalls/).

### 2. Put the application on the VPS

For the initial deployment, the simplest approach is to clone the repository on
the VPS and build the image there. A later automated deployment can instead
build an image in CI, push it to a private image registry, and have the VPS pull
that exact image. Do not copy a running container from the development machine;
deploy source or an immutable image.

On the VPS, create the production `.env` alongside the repository:

```dotenv
PINOCHLE_ADMIN_TOKEN=replace-this-with-a-long-random-secret
PINOCHLE_PUBLIC_BASE_URL=https://pinochle.example.com
```

Set restrictive permissions on it:

```console
chmod 600 .env
```

Compose already publishes Pinochle only on IPv4 loopback by default. Do not
set `PINOCHLE_BIND_ADDRESS=0.0.0.0` when a reverse proxy on the same server is
handling public traffic. Docker documents the three-part syntax as
`HOST_IP:HOST_PORT:CONTAINER_PORT` in its
[port-publishing guide](https://docs.docker.com/engine/network/port-publishing/).

Build and start the application on the VPS:

```console
docker compose --env-file .env -f docker/compose.yaml up --build --detach
docker compose --env-file .env -f docker/compose.yaml ps
```

Before configuring public HTTPS, verify the application from an SSH session on
the VPS:

```console
curl http://127.0.0.1:8000/healthz
```

The expected response is `{"status":"ok"}`.

### 3. Add the HTTPS reverse proxy

Caddy is a simple option because it obtains and renews certificates
automatically when the domain points to the VPS and ports 80 and 443 are
reachable. Install Caddy on the VPS and use this minimal Caddyfile, replacing
the example hostname:

```caddyfile
pinochle.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Start or reload Caddy using the service-management instructions for the way it
was installed. Caddy recognizes `text/event-stream` responses and flushes them
immediately, so the Pinochle SSE stream does not require a special buffering
directive. See Caddy's documentation for
[automatic HTTPS](https://caddyserver.com/docs/automatic-https) and
[`reverse_proxy` streaming](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#streaming).

Verify from a computer other than the VPS:

```console
curl https://pinochle.example.com/healthz
```

Then open `https://pinochle.example.com/admin` in a browser, sign in with the
administrator token, and confirm the generated player join links use the same
public HTTPS hostname (`PINOCHLE_PUBLIC_BASE_URL`).

### 4. Deploy updates

Schedule updates when no game is active because replacing the container loses
all in-memory state and disconnects every player. For a source-based deployment,
update the checked-out revision and then rebuild:

```console
docker compose --env-file .env -f docker/compose.yaml up --build --detach
docker compose --env-file .env -f docker/compose.yaml ps
docker compose --env-file .env -f docker/compose.yaml logs --tail 100 pinochle
```

Retain the previous source revision or image tag until the new container passes
its health check. If using a registry, deploy immutable version tags rather than
relying only on `latest`; that makes rollback unambiguous.

Back up the VPS configuration and `.env` securely, but do not expect a game-state
backup: the system intentionally has no persistent game storage. Monitor free
disk space because old Docker image layers and container logs accumulate even
though game data does not.

## Common problems

**`/` or `/admin` returns 404.** Verify that you are running a freshly built
image from this repository and that the build included `frontend/public` and
the compiled `frontend/dist` modules.

**Port 8000 is already allocated.** Stop the process using it or change the host
side of the mapping to another port, such as `8080:8000`.

**The container exits or remains unhealthy.** Read its logs with the command in
“Check status and logs.” Configuration errors and startup exceptions appear
there.

**Player links contain `localhost`.** Set `PINOCHLE_PUBLIC_BASE_URL` to an
address reachable from the players' devices, then recreate the container.

**Code changes do not appear.** Re-run `up --build --detach`; the running
container contains a snapshot created at build time.

**Players disconnect when the container restarts.** This is expected. SSE
connections and in-memory game state do not survive a restart.
