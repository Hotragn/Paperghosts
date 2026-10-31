# Resume

Where the build stands, for whoever picks it up next. The spec is `BRIEF.md`, the build order is `BUILD-PLAN.md`, and the reasons behind each choice are in `DECISIONS.md`. Each milestone ends with a STATUS block below, newest first.

Hard date: the site must be live on Oct 31.

## Next step

**Phase 2C: the reader** (`BUILD-PLAN.md` section 4), once Phase 2B's PR is merged. It starts with `POLICY.md` and the gold set, split by story id (decision 36).
- Lexicon v2 keeps all five rules (decision 31).

Needs the owner's yes when we get there:
- the Render deploy
- domain DNS

## STATUS: Phase 2B, schemas and data layer (2026-10-30)

Branch `phase-2b-data-layer`, in four steps, each reviewed by the EM; one PR into `main` at the end.

Built:
- **2B.1** (decisions 32 and 33):
  - Pydantic models for every collection, and Atlas validators generated from them
  - BinData embeddings
  - `make db-init`, which creates every collection and index and can run twice
  - `BUDGET.md`, a storage budget from real document sizes
- **2B.2** (decision 34):
  - the LCCN title parser, tested on 200 titles checked by hand
  - loc.gov title records, cached
  - the title lookup by LCCN
  - the GeoNames geocoder over the US, Puerto Rico and Virgin Islands dumps, with its manifest
  - the record check, which checks each paper's place against its title record's county
- **2B.3** (decision 35):
  - the reel-to-batch map
  - the page check, which looks at a page's size and its OCR before its crop is shown
  - `page_service`'s cache of every Library of Congress answer
  - CAPTCHA pages treated as busy
  - the EM's frame rule: where only the frame differs, the member's frame
- **2B.4** (decision 36):
  - reprint stories, in which a printing joins a story only by matching its first printing directly
  - their evaluation set, labelled and frozen before tuning, and a dev set to tune on

Measured:
- **Geocoder:** 98.0% (95.0–99.2%) of 200 papers' places are right with the record check, and 97.0% without it.
- **Reel-to-batch map:**
  - It names a batch for 370,949 of the 395,068 candidates with no batch path (93.9%).
  - With each issue hidden in turn, it gets 99.78% of issues right, and 85.3% on the 257 flagged reels.
- **Page check:** 0 false accepts of 90 frames beside the page (0–4.1%), and 2 false rejects of 85 own frames (0.6–8.2%).
- **Frames:** where only the frame differs, the member's frame was the page in 18 of 18. That changes 20,247 candidates' stored service.
- **Stories:**
  - Precision per candidate is 100% (97.7–100%), against eval A's 98.0%, and recall is 84.7% (79.0–89.1%).
  - The chaining in 54 of the 207 largest clusters is split in 51.
  - v2 has 974,399 distinct stories. Decision 36's skip rule would have made the reader's job 1,002,205 printings, but the EM's call keeps the reader on every triaged candidate.
- **Storage:** the top of the range, 62,402 stories, needs 461.8 MB as stored, so it fits on M0 only without `sample_mflix`.
- **Requests to the Library of Congress:**
  - 2B.2's title records: 327 in the final build and 177 for the 200 pairs.
  - 2B.3's measurements: 549, against the 600 planned.

Gate:
- Tests and lint pass. `make db-init` runs twice.
- The budget is written down (`BUDGET.md`).
- Geocoder accuracy is measured on a sample of 200, with and without the record check.
- The map's hit rate on hidden issues is reported, and all 257 reels with more than one batch are flagged in `reels.json`.
- The page check's error rates are measured, with intervals.
- The clustering evaluation set's sha256 is in `eval/clusters/frozen.json`, pushed before tuning. Its precision and recall are measured, and every chained large cluster is explained and its fix measured.
- Every claim of a push was checked with `git ls-remote`.

Risks and open questions:
- **`places_search` waits on the owner:** `sample_mflix` holds M0's third Search slot (decision 33).
- **Storage:** if the reader's real count needs more than M0 has, it's the owner's call (`BUDGET.md`).
- **The stories miss reprints:**
  - Eval A's links miss reprints whose openings differ. The body probe found 76 of 80 such pairs to be one story. 2D measures adding the body's links on a fresh draw.
  - The stories split 15% of true reprints, mostly through OCR noise.
  - Three large clusters still join two texts that each hold a short first printing.
- **loc.gov lookups and the page check:**
  - 24,119 candidates with no batch path sit on reels the map doesn't know. They need loc.gov, and only for reports.
  - The page check costs 2 requests and about 1 MB of ALTO a page. About 21,000 checks would cache about 4 GB, inside the 10 GB data budget only if gzipped or reduced to each result (2D).
- **In-sample choices:**
  - The page check's threshold, a fifth, came from 38 calibration pages. The 90 measured pairs were fresh.
  - The geocoder's two in-sample rules: 2D measures them on a fresh draw (decision 34).
- **The reader reads every triaged candidate, 1,236,122** (the EM's call on decision 36). Stories stay the unit for display and counts. The Tinker credit check weighs the job before 2C's full pass, and a shortfall goes to the EM and the owner.

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
