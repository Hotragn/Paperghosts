# Resume

Where the build stands, for whoever picks it up next. The spec is `BRIEF.md`, the build order is `BUILD-PLAN.md`, and the reasons behind each choice are in `DECISIONS.md`. Each milestone ends with a STATUS block below, newest first.

Hard date: the site must be live on Oct 31.

## Next step

**Phase 2B: schemas and data layer** (`BUILD-PLAN.md` section 4), once PR #2 is merged. Lexicon v2 (decision 30) waits on the EM. If it is accepted, its re-read runs before anything is loaded into Atlas.

Needs the owner's yes when we get there:
- the Render deploy
- domain DNS

## STATUS: Phase 2A, archive read and EDA (2026-10-30)

Branch `phase-2a-archive`, PR #2.

Built:
- Lexicon v1, with OCR variants, and the near-miss lexicon (decisions 19–21). `IngestArchiveWorkflow` and `make ingest`, which skip a year only while every output's hash matches (decisions 22–24).
- The full read of all 180 AmericanStories year files at revision `77e27fa6` (decision 25).
- Crops, one per box, fetched once and cached, and the display headline without its masthead lines (decisions 26 and 28).
- Eval A (`make eval`, 42 s, 4.0 GB at peak). It produces the EDA, the candidates' composition, the lexicon's recall and eight charts (decisions 27, 29 and 30).

Measured:
- 370,313,913 articles in 16,887,460 pages, giving 1,050,459 candidates (2,837 per million) and 6,872,539 near-miss articles.
- The read took 118.6 min for 340.4 GB, at 47.8 MB/s with four years at a time.
- 3.5% of candidates are ghost reports (1.7–7.0%), about 36,800. Reprints put 31.4% of candidates in 80,770 clusters, which leaves 801,071 distinct stories.
- Lexicon v1 finds about 49% of the ghost reports, and at least 27%. That rests on 4 reports found among 38,900 non-candidates (decision 30).
- The crop check passes 48 of 50 (86.5–98.9%). The display headline drops 7,509 lines at 158 of 158 precision on the judged sample (97.6–100%).
- 32.0% of candidates have no batch path, and 92.4% of those are on reels whose batch is known (decision 29).

Gate:
- All 180 years are done, and none failed. Six ran twice: 1872 and 1889 lost their streams, and kill test 1 cost 1881–1884 their first attempts (decision 25).
- Disk: the outputs take 1.94 GB (`data/candidates` 1.3 GB, `data/samples` 565 MB, counts 956 KB, manifests 720 KB), and 39 GiB are free.
- `make ingest YEARS=1850` reproduces 1850. With its candidates moved aside, a rerun wrote all three outputs byte-identical, with the sha256 in the committed manifest.
- Kill-test evidence: `eval/results/phase2a/kill-test-1.md`, with Temporal UI screenshots from before and after (`kill-test-1-*.png`).
- Both crop-check failures are explained: #21 is AmericanStories' stray box, recorded as a known limitation (decision 29), and #50 is a 1964 page with no loc.gov item.
- The EM's spot check, seed "EM spot-check 2A", read 20 random candidates and 10 random non-candidates against their stored text:
  - every candidate's term is in its text
  - none of the 10 non-candidates is a report
  - 1 of the 20 candidates is a report, in line with 3.5%

Risks and open questions:
- **Lexicon v2 is the EM's call** (decision 30). Spiritualist terms would add about 161,000 candidates (+15%) and catch 3 of the 4 missed reports. Adding them takes a full re-read: 118.6 min and 340.4 GB.
- The recall estimate rests on 4 reports, 2 of them borderline. Its screen would still catch only 5 of eval A's 7 reports once their lexicon terms are masked.
- `POLICY.md` (2C) has to settle delusions, hallucinations, spirit control and a felt presence of the dead.
- 25,595 candidates need loc.gov to name their page's IIIF service, and its JSON API allows 20 requests a minute. 2B looks them up only for reports (decision 29).

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
