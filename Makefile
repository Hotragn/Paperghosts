.PHONY: setup lint test web keys temporal worker smoke api app ingest eval eval-v1 db-init db-verify numbers

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

# eval A over the read in data/, lexicon v2's: its EDA in eval/results/eval_a_v2/, then v2
# against v1 (decision 31)
eval:
	uv run python scripts/eval_a.py
	uv run python scripts/lexicon_v2.py

# eval A's record of lexicon v1, from its read in data/archive/lexicon-v1
eval-v1:
	uv run python scripts/eval_a.py data/archive/lexicon-v1

api:
	uv run uvicorn api.main:app --port 8000

# the API and the web shell together
app:
	$(MAKE) -j2 api web

db-init:
	uv run python -m paperghosts.store.db_init

# Later targets fail on purpose until their phase builds them.
db-verify:
	@echo "make $@ is built in Phase 2D"; exit 1

numbers:
	@echo "make $@ is built in Phase 5A"; exit 1
