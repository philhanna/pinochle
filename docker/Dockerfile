# Backend-only image: the API and SSE server, with no front end yet
# (docs/design.md §10 describes a two-stage build that compiles frontend/
# with Node; that stage is added once the front end exists — design.md's
# own build order puts it after the server, in step 8).
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
