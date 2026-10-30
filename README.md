# Paper Ghosts

Type a US town and read the ghost reports its newspapers printed between 1774 and 1963. The reports come from the AmericanStories dataset and the Library of Congress page scans. The site never writes a ghost story: every claim links to the clipping it came from.

This is a work in progress. The plan is in [`Docs/BUILD-PLAN.md`](Docs/BUILD-PLAN.md), and where the build stands is in [`Docs/RESUME.md`](Docs/RESUME.md).

## Run it

You need `uv`, Node with `pnpm`, the Temporal CLI and Ollama. Keys go in `.env`, which git ignores.

| Command | What it does |
|---|---|
| `make setup` | Installs the Python 3.12 environment and the web shell's packages |
| `make lint` | ruff, oxlint and the TypeScript check |
| `make test` | pytest, offline; the Temporal test starts its own throwaway server |
| `make keys` | Checks every key by shape and with one cheap call, and never prints a value |
| `make temporal` | The Temporal dev server, with its state in `data/temporal/` and its UI at http://localhost:8233 |
| `make worker` | The Temporal worker |
| `make smoke` | One workflow whose activity heartbeats, fails once on purpose and recovers through its retry policy; needs `make temporal` and `make worker` running |
| `make ingest YEARS="1850 1910"` | Streams those year files through the prefilter, four at a time, and writes each year's candidates, counts, samples and manifest under `data/`; with no `YEARS`, every year in the dataset. A year that is already done is skipped. Needs `make temporal` and `make worker` running |
| `make api` | The read-only API at http://localhost:8000 |
| `make web` | The web shell at http://localhost:5173 |
| `make app` | `make api` and `make web` together |

`make eval`, `make db-init`, `make db-verify` and `make numbers` print the phase that builds them and exit with an error.

The walking skeleton takes one 1850 article from the archive, through Atlas and the API, to a page that shows its clipping beside its text:

```bash
uv run python scripts/phase1_env.py     # environment facts; saves the 1850 Stratford articles
uv run python scripts/load_skeleton.py  # loads the Lewistown gazette's knockings into Atlas
make app
```

## What it can't do

Filled in as limits are found.

## Failure log

Filled in as failures are found.

## Credits

- Article text: AmericanStories, from Harvard's Dell Research (CC-BY-4.0)
- Page scans: Library of Congress, Chronicling America (public domain)

The code is MIT licensed; see [LICENSE](LICENSE).
