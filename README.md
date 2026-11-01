# Paper Ghosts

<img src="web/public/brand/logo.svg" alt="" width="96" height="96">

A morgue of ghost reports from American newspapers, 1774–1963. Paper Ghosts reads the AmericanStories OCR of the Library of Congress's page scans, picks out the articles that report a ghost, and files each one with the exact words of the scan that state its place, what was seen and how it ended. The site never writes a ghost story: every value on it is a quote, and every report links to its clipping.

## The demo: the Morgue

The 78 ghost reports among the 450 frozen evaluation articles, each with its clipping beside its transcription, the quotes marked in the text, and a typed index card that says "Not stated" wherever the paper didn't say. There's no server and no database behind it, and it works offline.

```bash
make setup                     # once: the Python environment and the web packages
pnpm --dir web build
pnpm --dir web preview         # http://localhost:4173
```

`uv run python scripts/export_demo.py` rebuilds its data, `web/public/reports.json` and the clippings in `web/public/crops/`, from the frozen labels and the local crop cache, and fetches nothing.

### Its rooms
- **The drawer:** search by town, state or word, and filter by decade, outcome and the state the paper was printed in.
  - Each report opens into its clipping beside its transcription, with the verified quotes marked.
  - An index card lists every field, VERIFIED or "Not stated".
  - It gives the paper's own place, labelled as the paper's, not the story's.
  - It lists the five ghosts like it.
- **Paper samples:** the clearest scan for each outcome, captioned only with its verified quotes.
- **How we know:** every figure from the numbers sheet, with its interval, including the teacher benchmark.

It runs live at [paper-ghosts.onrender.com](https://paper-ghosts.onrender.com), a static site: `render.yaml` builds `web/` and publishes `web/dist`. The bundle holds no keys.

### MongoDB Atlas
```bash
uv run python scripts/load_demo_atlas.py               # upserts the 78 into paperghosts.reports; never deletes
uv run python scripts/query_demo_atlas.py "apparition" # Atlas Search, fuzzy: finds the OCR's "apparilion"
uv run python scripts/query_demo_atlas.py --like <article_id>   # ghosts like this one (moreLikeThis)
```

```bash
uv run python scripts/load_demo_places.py load                       # the papers' 46 towns, geocoded from GeoNames
uv run python scripts/load_demo_places.py near Philadelphia Pennsylvania 250   # $geoNear: papers printed nearby
```

The keys come from `MONGODB_URI` in `.env`.
- "Near this town" is about where the papers were printed, never where the stories happened.
- Atlas Vector Search isn't built yet. The index is there for 384-dimension vectors, but Hugging Face's Inference Providers credits for an open embedding model ran out (HTTP 402), and the owner chose to spend nothing. Until then, "ghosts like this one" is Atlas Search's moreLikeThis.

### Sentry
- **API:** `/api/search` and `/api/like/{id}` run each Atlas query in a span of op `db.atlas.query`, with its kind and latency, never the words searched for. The scripts' queries run the same way.
- **Releases** are commits.
- **Figures:** `uv run python scripts/sentry_latency.py [SINCE [RELEASE]]` pulls p50 and p95 per query kind with `SENTRY_AUTH_TOKEN`. One real finding is fixed: decision 40.
- **The web app** sends tracing and errors only when built with `VITE_SENTRY_DSN`.
  - With `SENTRY_AUTH_TOKEN` at build time, it uploads hidden source maps for the commit and deletes them from `dist`.
  - On Render, set both in the service's environment.
- The reports go in as the planned `Report` documents, and Atlas's own validator checks them.
- The site's "ghosts like this one" is Atlas's answer, saved by `scripts/export_like.py`, so the static build works offline.
- Sample outputs are in `Docs/demo/`.

## The numbers

```bash
uv run python scripts/article_numbers.py
```

This prints every figure the write-up uses, each beside the committed results file or doc line it was read from, and writes them to `eval/results/numbers.json`. Among them:
- the archive: 370 million articles on 16.9 million pages
- the 1,236,122 articles the lexicon flags, which group into 974,399 distinct stories
- the gold set, and how far its two labelling passes agree
- the teachers compared on dev

## How it was made, and where it stands

- **Ingest and evaluation A** stream all 180 year files through a ghost-word prefilter, then measure what it keeps and misses on samples judged by hand (`Docs/DECISIONS.md`).
- **Stories** group reprints of one story across papers, so each story is read once.
- **Gold and dev,** 300 and 150 articles drawn across 17 strata, are labelled one article at a time under `eval/gold/POLICY.md` by an AI labeller (Claude), in a labelling page that shows the crop beside the text.
  - A blind second pass relabelled all of gold and a seeded fifth of dev.
  - Fresh judges ruled every disagreement again, blind.
  - The labels are frozen by sha256 before any model output touched them.
- **The reader is not trained yet.** Its training labels will come from an open-weight teacher run locally on this Mac; labels never come from Claude, and gold and dev are kept for evaluation only. Two teachers were compared on dev (`eval/results/phase2c/`):
  - Qwen3.5-397B-A17B, through Tinker, until the spend stopped
  - gemma4:26b-a4b-it-qat, through Ollama
- **The student** is Qwen3.5-4B, to be fine-tuned with LoRA through mlx-lm.

## What it can't do yet

- The archive-wide pass hasn't run, so the demo shows only the 78 evaluation reports, not every ghost the papers printed.
- The OCR is shown as printed. Some clippings are hard to read, and a quote is only as good as the scan's text.
- A place is the paper's own words. Nothing is geocoded or mapped yet.

## AI disclosure
- **Claude** wrote the code, under the owner's direction, and labelled the 450 evaluation articles under the labelling policy, one at a time. The second pass and the blind re-rulings were done by separate Claude judges that couldn't see the first labels.
- **Open-weight models do the reading:** Qwen3.5-397B through Tinker and gemma4:26b on this Mac were scored as teachers on dev. Training labels never come from Claude.
- **Entire** recorded every agent session; `Docs/demo/entire_sessions.md` points to two of them.

## Brand
`Docs/BRAND.md` covers the brand: the hand-drawn mark (`web/public/brand/`), the colour tokens with their WCAG AA check (`scripts/check_contrast.py`), the type and the voice.

## Data and licences

- Article text: AmericanStories, from Harvard's Dell Research (`dell-research-harvard/AmericanStories`, CC-BY-4.0)
- Page scans and clippings: Library of Congress, Chronicling America (no known copyright restrictions)
- Fonts, self-hosted through Fontsource under the SIL Open Font License: UnifrakturMaguntia, Bodoni Moda, Newsreader and Courier Prime
- Open-weight models: Qwen3.5-397B-A17B and Qwen3.5-4B (Qwen), and gemma4:26b-a4b-it-qat (Google)
- The code is MIT licensed; see [LICENSE](LICENSE).

## Development

The plan is in [`Docs/BUILD-PLAN.md`](Docs/BUILD-PLAN.md), and where the build stands is in [`Docs/RESUME.md`](Docs/RESUME.md).

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
| `make ingest YEARS="1850 1910"` | Streams those year files through the prefilter, four at a time, and writes each year's candidates, counts, samples and manifest under `data/`; with no `YEARS`, every year in the dataset. A year is skipped while its manifest matches the pinned dataset revision and the current code, and every output on disk matches its recorded sha256. Needs `make temporal` and `make worker` running |
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
