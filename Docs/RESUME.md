# Resume

Where the build stands, for whoever picks it up next. The spec is `BRIEF.md`, the build order is `BUILD-PLAN.md`, and the reasons behind each choice are in `DECISIONS.md`. Each milestone ends with a STATUS block below, newest first.

Hard date: the site must be live on Oct 31.

## Next step

**Phase 2B: schemas and data layer** (`BUILD-PLAN.md` section 4), on branch `phase-2b-data-layer`.
- **Step 2B.1 is built**, and waits on the EM's review (decisions 32 and 33): the models and validators, the BinData check, `make db-init` and `BUDGET.md`.
  - **Pending:** `places_search`. `sample_mflix` holds M0's third Search slot, and freeing it is the owner's call.
  - **The owner's call:** what to do if the reader's real count needs more storage than M0 has (`BUDGET.md`). The EM takes both to the owner.
- **Step 2B.2,** the geocoder and LCCN parser, follows the review.
- Lexicon v2 keeps all five rules (decision 31).

Needs the owner's yes when we get there:
- the Render deploy
- domain DNS

## STATUS: Phase 2A, archive read, EDA and lexicon v2 (2026-10-30)

Branches `phase-2a-archive` (PR #2, merged) and `phase-2a-lexicon-v2` (PR #3, step 2A.8).

Built:
- Lexicon v1, with OCR variants, and the near-miss lexicon (decisions 19–21). `IngestArchiveWorkflow` and `make ingest`, which skip a year only while every output's hash matches (decisions 22–24).
- Lexicon v2, which adds five spiritualist rules and records in each candidate's `terms` the rules that matched it (decision 31).
- Two full reads of all 180 AmericanStories year files at revision `77e27fa6`:
  - v1's (decision 25), now archived in `data/archive/lexicon-v1/`
  - v2's (decision 31)
- Crops, one per box, fetched once and cached, and the display headline without its masthead lines (decisions 26 and 28).
- Eval A (`make eval`, 93 s, 4.7 GB at peak):
  - It produces the EDA, the candidates' composition, the lexicon's recall and eight charts (decisions 27, 29 and 30).
  - It then compares v2 with v1, and measures a judged sample of v2's added candidates (decision 31).
  - `make eval-v1` reproduces v1's record from the archive.

Measured:
- 370,313,913 articles in 16,887,460 pages. Lexicon v2 gives 1,236,122 candidates (3,338 per million) and 6,695,792 near-miss articles. v1 gave 1,050,459 (2,837 per million).
- Each read takes about two hours for 340.4 GB, with four years at a time: 118.6 min for v1 and 120.6 min for v2.
- Ghost reports: 3.5% of v1's candidates (1.7–7.0%), about 36,800, and 7.0% of the 185,663 that v2 adds (4.2–11.4%), about 13,000 more.
- Reprints put 30.3% of v2's candidates in 91,301 clusters, which leaves 952,591 distinct stories.
- Recall:
  - Lexicon v1 finds about 49% of the ghost reports, and at least 27% (decision 30).
  - Lexicon v2 finds about 84%, and at least 48%. **v2's figures are in-sample:** its rules were chosen from that screen's misses.
  - 2C's eval B gives the independent figure (decision 31).
- The crop check passes 48 of 50 (86.5–98.9%). The display headline drops 7,509 lines at 158 of 158 precision on the judged sample (97.6–100%).
- 32.0% of v2's candidates have no batch path, and 93.0% of those are on reels whose batch is known (decisions 29 and 31).

Gate:
- All 180 years are done in both reads, and none failed.
  - In v1's read, six ran twice: 1872 and 1889 lost their streams, and kill test 1 cost 1881–1884 their first attempts (decision 25).
  - In v2's read, every year finished at the first attempt, all at code version `2d6ff0faaf81`.
- v1 ⊆ v2: all 1,050,459 v1 candidates are still candidates, and none of the 185,663 added holds a v1 term.
- Disk: the v1 archive and v2's outputs take 4.1 GB, within the 10 GB budget, and 36 GiB are free.
  - `data/archive/lexicon-v1`: 1.8 GiB
  - v2's `data/candidates`: 1.5 GiB
  - v2's `data/samples`: 563 MiB
- `make ingest YEARS=1850` reproduces 1850 under both lexicons. With its candidates moved aside, a rerun wrote all three outputs byte-identical, with the sha256 in the manifest.
- `make eval-v1` reproduces eval A's v1 record byte for byte, apart from `generated_at`.
- Kill-test evidence: `eval/results/phase2a/kill-test-1.md`, with Temporal UI screenshots from before and after (`kill-test-1-*.png`).
- Both crop-check failures are explained: #21 is AmericanStories' stray box, recorded as a known limitation (decision 29), and #50 is a 1964 page with no loc.gov item.
- The EM's spot check of v1, seed "EM spot-check 2A", read 20 random candidates and 10 random non-candidates against their stored text:
  - every candidate's term is in its text
  - none of the 10 non-candidates is a report
  - 1 of the 20 candidates is a report, in line with 3.5%

Risks and open questions:
- **The ouija rule stays.** None of its 6 sampled candidates is a report (0–39%). The EM kept it, and 2C's term strata measure it (decision 31).
- Each new rule's marginal yield rests on 0 to 4 reports, so its interval is wide (decision 31).
- v2's 84% recall is in-sample. The screen behind both lexicons' recall rests on 4 reports, 2 of them borderline. Even with their lexicon terms masked, it would still catch only 5 of eval A's 7 reports.
- v2's gain rests on 14 reports in 200, 2 of them borderline.
- `POLICY.md` (2C) has to settle these cases:
  - delusions and hallucinations
  - spirit control and a felt presence of the dead
  - decision 31's two borderline kinds
- 27,817 of v2's candidates need loc.gov to name their page's IIIF service, and its JSON API allows 20 requests a minute. 2B looks them up only for reports (decision 29).
- The reader's job is 1,236,122 candidates, 17.7% more than v1's. The Tinker credit check weighs that before the full pass.

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
