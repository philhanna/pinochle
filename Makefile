# Development tasks.  See docs/impl.md for how these fit the slice workflow.

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
# No lockfile and no global install: npx fetches the compiler on first use and
# caches it.  A local `npm install` in frontend/ takes precedence if present.
TSC ?= npx -y -p typescript@5 tsc

.DEFAULT_GOAL := help
.PHONY: help test build watch dev dev-fast seed seed-watch seed-all docker docker-logs docker-down clean

help:  ## List the available targets
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| sed 's/:.*## /\t/' \
		| awk -F'\t' '{printf "  %-14s %s\n", $$1, $$2}'

test:  ## Run the Python test suite
	$(PYTHON) -m pytest

build:  ## Compile frontend/src to frontend/dist
	cd frontend && $(TSC)

watch:  ## Recompile the front end on every save
	cd frontend && $(TSC) --watch

dev: build  ## Run the server on localhost with reload (admin token: dev)
	./scripts/dev.sh

dev-fast: build  ## Same, with every server-side pause set to zero
	PINOCHLE_COMPUTER_DELAY_SECONDS=0 PINOCHLE_TRICK_CLEAR_SECONDS=0 ./scripts/dev.sh

seed:  ## Create a game (SOUTH human), print join links, start when SOUTH joins
	$(PYTHON) scripts/seed.py

seed-watch:  ## Create and start an all-computer game to watch
	$(PYTHON) scripts/seed.py --humans none

seed-all:  ## Create a four-human game; start it once all four tabs are open
	$(PYTHON) scripts/seed.py --humans NORTH,EAST,SOUTH,WEST

docker:  ## Build and run the image, front end included
	cd docker && docker compose up --build -d
	@echo "http://localhost:8000/admin — token from: make docker-logs"

docker-logs:  ## Follow the container log
	cd docker && docker compose logs -f

docker-down:  ## Stop and remove the container
	cd docker && docker compose down

clean:  ## Remove build and test artefacts
	rm -rf frontend/dist .pytest_cache
	find . -name __pycache__ -type d -not -path './.venv/*' -prune -exec rm -rf {} +
