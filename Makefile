.PHONY: setup lint test web keys temporal worker smoke api app ingest eval db-init db-verify numbers

setup:
	uv sync --locked
	pnpm --dir web install --frozen-lockfile

lint:
	uv run ruff check .
	uv run ruff format --check .
	pnpm --dir web lint
	pnpm --dir web exec tsc -b

test:
	uv run pytest

web:
	pnpm --dir web dev

keys:
	uv run python scripts/check_keys.py

temporal:
	mkdir -p data/temporal
	temporal server start-dev --db-filename data/temporal/temporal.db

worker:
	uv run python -m paperghosts.workflows.worker

smoke:
	uv run python -m paperghosts.workflows.smoke

ingest:
	uv run python -m paperghosts.workflows.ingest $(YEARS)

api:
	uv run uvicorn api.main:app --port 8000

# the API and the web shell together
app:
	$(MAKE) -j2 api web

# Later targets fail on purpose until their phase builds them.
eval:
	@echo "make $@ is built in Phase 2A"; exit 1

db-init:
	@echo "make $@ is built in Phase 2B"; exit 1

db-verify:
	@echo "make $@ is built in Phase 2D"; exit 1

numbers:
	@echo "make $@ is built in Phase 5A"; exit 1
