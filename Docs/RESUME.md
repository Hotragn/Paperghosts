# Resume

Where the build stands, for whoever picks it up next. The spec is `BRIEF.md`, the build order is `BUILD-PLAN.md`, and the reasons behind each choice are in `DECISIONS.md`. Each milestone ends with a STATUS block below, newest first.

Hard date: the site must be live on Oct 31.

## Next step

**Phase 2A: the archive read and EDA** (`BUILD-PLAN.md` section 4), once PR #1 is merged.

Needs the owner's yes when we get there:
- the Render deploy
- domain DNS

## STATUS: Phase 1, scaffolding and environment (2026-10-29)

Branch `phase-1-scaffold`, PR #1. The gate checklist is on the PR.

Built:
- The ARCHITECTURE section 5 layout, the `uv` project on Python 3.12, the pnpm web shell, and a Makefile whose later-phase targets name their phase.
- `make keys`: a shape check and one cheap authenticated call per key; all 16 keys are OK, and no value is ever printed (decision 13).
- The Sentry helper, which collects nothing about people (decision 15), and the Temporal dev server, worker and smoke workflow.
- `eval/results/phase1_env.json`, written by `scripts/phase1_env.py` at `9f53354`.
- The walking skeleton: the Lewistown gazette's 1850-07-26 "Mysterious Knockings" goes from Atlas through FastAPI to a page with its IIIF crop, and the crop matches its text (`eval/results/phase1/skeleton.png`).
- CI: ruff, offline pytest, the web lint, typecheck and build, and gitleaks over the full history.

Measured, all from `eval/results/phase1_env.json`:
- Machine: Apple M4, 10 cores, 24.0 GiB of RAM, 26.2 GiB of free disk.
- `faro_1850`: 989,144,629 bytes downloaded in 12.0 s, at 82.4 MB/s. It holds 24,664 pages and 733,880 articles.
- Parsing on one core: 3,835 pages/s and 114,100 articles/s (153.8 MB/s compressed), so 0.5 cores keep up with one download. Ingest is limited by the network, not the CPU.
- 20 articles of 1850 mention Stratford and knocking; 2 name Phelps.
- Ollama `gemma4:26b-a4b-it-qat`: 31.0 generated tokens/s, after a 10.5 s load.
- Atlas 8.0.34: 239,243,264 bytes used, 239,185,920 of them by `sample_mflix`. A Search index and a Vector Search index each became queryable in 23.5 s, then were dropped.
- SerpApi: 210 searches left.
- Ultramarine `ultramarine-1-flash`: one tiny completion used 27 tokens and took 2.04 s.
- Tinker: 35 base models, among them `Qwen/Qwen3.5-4B` and `Qwen/Qwen3.5-397B-A17B`, both trainable and sampleable.
- Sentry: the test event could be read back from `paperghosts-api` after 10.6 s.

Unknown, so null in the JSON with its reason:
- The Atlas tier and storage limit. The owner can tell us, or an Atlas API key would.
- Tinker credits. Only the console shows the balance.
- The Ultramarine cost. The API reports tokens only, so INV-9's "actual cost" needs Paper Instruments' price sheet.
- Whether trained LoRA weights download. The SDK documents it; Phase 2C verifies it.

Risks and open questions:
- Atlas: if the cluster is the free tier, `sample_mflix` already fills most of it. Dropping it is the owner's call.
- Crops: 9 of the 20 matching 1850 pages have no `raw_data_loc`, so their batch comes from loc.gov (decision 18). One bounding crop is right only for single-column articles, and AmericanStories headlines can include the page masthead.
- Speeds varied between the two runs of the script, the parse rate and Gemma's above all, so Phase 2A re-measures at scale before it sets the concurrency.
- Disk: free space dropped between the two runs because macOS swap grew while Gemma loaded. Don't run Gemma during the ingest.
- Before any session is published, redact another local account's process list from this phase's Entire logs (step 1.7's note).

## Setup before Phase 1 (2026-10-29)

- The private GitHub repo `Hotragn/Paperghosts` is cloned here.
- `.gitignore` covers `.env` and keeps `Docs/IDEAS.md` private.
- `.env` holds the keys, never displayed. The SerpApi and Ultramarine keys are set too; the Ultramarine one is named `PAPERINSTRUMENTS_API_KEY` (decision 12).
- Entire session capture is enabled for Claude Code in this repo only. Checkpoints sync to `origin` on push.
- Sentry: projects `paperghosts-api` (Python/FastAPI) and `paperghosts-web` (React) exist in org `hotragn`. Their DSNs are `SENTRY_DSN` and `SENTRY_DSN_WEB`, and an auth token with read access is in `.env`. The GitHub repo is linked in Sentry.
