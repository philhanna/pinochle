# Two-stage build: the TypeScript client is compiled by Node, then copied
# into a Python runtime image that carries no Node at all.
#
# The client is compiled here rather than copied from the host so that the
# image can never serve a stale frontend/dist — which is also why
# .dockerignore excludes that directory (docs/impl.md D3).  No package
# lockfile is involved: the compiler is the only build dependency, pinned to
# a major version.
FROM node:22-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/tsconfig.json ./
COPY frontend/src ./src
RUN npx -y -p typescript@5 tsc


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PINOCHLE_FRONTEND_DIR=/app/frontend

WORKDIR /app

# Dependencies first, so a code change does not re-resolve them.
COPY pyproject.toml README.md ./
COPY pinochle ./pinochle
RUN pip install --no-cache-dir .

# The client: hand-written static files from the repo, compiled modules from
# the Node stage.  main.py serves public/ at /assets and dist/ at /static.
COPY frontend/public ./frontend/public
COPY --from=frontend /build/dist ./frontend/dist

RUN useradd --system --uid 10001 --create-home pinochle
USER pinochle

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2).status==200 else 1)"

# --workers 1 is mandatory, not a default: a second worker would hold a
# second, empty in-memory game state and a second SSE hub (design.md §4.7).
CMD ["uvicorn", "pinochle.web.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--timeout-keep-alive", "75", "--no-access-log"]
