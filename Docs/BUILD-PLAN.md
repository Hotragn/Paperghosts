# Build plan

How the build runs: five phases, each split into milestones, each milestone with a persona, deliverables and an exit gate. An engineering manager (EM) session writes the prompt for each milestone, a build session carries it out, and the EM checks the result before the next milestone starts.

## 1. How each milestone runs
1. **The EM sends the milestone prompt:** its scope, its deliverables, and the gate it must pass.
2. **The build session works on a branch** named `phase-<n>-<slug>`.
   - Small commits, pushed to the private repo, with a pull request into `main`.
   - It ends with a STATUS block in `RESUME.md`.
   - Its final message starts with one line: `<milestone>: GATE PASSED` or `<milestone>: BLOCKED — <reason>`.
3. **The EM reviews:**
   - reads the diff, and re-runs the gate commands
   - spot-checks outputs against their sources, using a random sample
   - checks the non-negotiables: no secrets, no invented numbers, verified quotes, respect for the dead
   - checks that CI is green
4. **Pass:** the EM merges the pull request and sends the next prompt. **Fail:** the EM sends a numbered fix list, and the gate runs again.
5. **Owner gates** always stop and ask first: making the repo public, deploying, DNS, posting anywhere, and spending money.

## 2. Phases and how they map to `BRIEF.md`
| Phase | Persona | `BRIEF.md` step | Milestones |
|---|---|---|---|
| 1 Scaffolding and environment | Systems architect, DevOps | Step 1, the setup part | 1 |
| 2 Database, schemas and data models | Data engineer, data architect, ML specialist | Step 1 (archive read), Step 2, Step 3 | 2A archive read and EDA; 2B schemas and data layer; 2C reader; 2D load, cluster and harvest |
| 3 Backend and APIs | Software engineer, ML specialist | Step 4, plus the API part of Step 5 | 3A investigator; 3B API and static export |
| 4 Frontend and integration | UI and UX specialist, software engineer, product manager | Step 5 | 4A brand and design system; 4B pages and integration; 4C deploy (owner's yes); 4D walks (owner's call) |
| 5 Polish and QA | QA engineer, DevOps, product manager | Step 6 | 5A QA and hardening; 5B launch assets and the post |

## 3. Phase 1: scaffolding and environment
**Persona:** systems architect and DevOps engineer.

**Deliverables**
- The planning docs and repo config committed.
- The repo layout from `ARCHITECTURE.md` section 5, the `uv` project, and the `pnpm` web shell.
- A Makefile. Targets that belong to later phases exist as stubs that say which phase builds them.
- `config.py`, plus `make keys`: a shape check for every key and one cheap authenticated call per service, printing only the name, OK, FAIL or EMPTY, and a reason.
- The Temporal dev server (`make temporal`, persisting under `data/temporal/`), a worker, and a smoke workflow with a heartbeat and a retry policy (`make smoke`).
- Environment facts, written by a script to `eval/results/phase1_env.json`:
  - Tinker: credits, the base models available for LoRA training and sampling, and whether trained weights can be downloaded
  - Atlas: tier, version, storage limit and storage used, and whether Atlas Search and Vector Search indexes can be created (create one of each on a scratch collection, then drop it)
  - Sentry: one test event sent, then read back through the API
  - SerpApi: searches left, read from the account endpoint
  - Ultramarine: one minimal call, with the model ID and the cost or usage it reports
  - Ollama: tokens per second for `gemma4:26b-a4b-it-qat`
  - the machine: cores, RAM and free disk
  - for `faro_1850`: download speed, plus parse speed in pages and articles per second on one core
- A walking skeleton: one real 1850 article (the Stratford, Conn. "knockings" report from the first probe) goes into a scratch Atlas collection, out through an API endpoint, and onto a web page that shows the IIIF crop next to the text.
- CI on GitHub Actions: `ruff`, offline `pytest`, a web typecheck and build, and a secret scan.
- Sentry init helpers for the API and the pipeline. They do nothing when no DSN is set, and they send no PII.
- A README skeleton, numbered entries in `DECISIONS.md`, and a STATUS block in `RESUME.md`.

**Exit gate**
- `make setup`, `make keys`, `make smoke` and `make test` pass. The output of `make keys` contains no secret values.
- CI is green on the pull request.
- `git ls-files` shows no `.env` and no `Docs/IDEAS.md`, and the secret scan is clean.
- The skeleton page shows the real crop, and the crop matches its text.
- `phase1_env.json` was produced by a script, and the numbers in `RESUME.md` match it.
- `entire status` shows Entire enabled.

## 4. Phase 2: database, schemas and data models

### 2A: archive read and EDA
**Persona:** data engineer, with a systems specialist for throughput.
- Lexicon v1, with OCR variants and unit tests, plus a near-miss lexicon.
- `IngestArchiveWorkflow` over all 180 files: candidates, counts, samples and manifests, with concurrency set from Phase 1's measurements.
- Kill test 1, with Temporal UI screenshots from before and after.
- The crop check on 50 random candidates spread across batches.
- Eval A, with charts:
  - per year: pages, articles and candidates, and candidates per million articles
  - by state, the term mix and the OCR-quality distribution
  - the reprint signal, and candidate lengths
- Prefilter recall: the random-sample bound and the near-miss pool. If misses are found, lexicon v2 and a re-run.

**Gate**
- All 180 years are done, or each failure is listed with its reason.
- Disk use is reported.
- `make ingest YEARS=1850` reproduces the 1850 counts exactly.
- Kill-test evidence exists, and every crop-check failure is explained.
- The EM spot-checks 20 random candidates and 10 random non-candidates against their sources.

### 2B: schemas and data layer
**Persona:** data architect.
- Pydantic models, with Atlas validators generated from them.
- `make db-init` creates every collection and index, and can be re-run safely.
- A storage budget built from real document sizes, and a written decision on what goes into Atlas.
- The GeoNames geocoder and its manifest. The LCCN title parser, tested on at least 200 distinct titles.
- The reprint-clustering design, and its evaluation set.

**Gate**
- Schema tests pass, and `make db-init` can run twice.
- The budget is written down.
- Geocoder accuracy is measured on a sample.

### 2C: the reader
**Persona:** ML specialist.
1. Write `POLICY.md`, build the gold set, freeze it and hash it.
2. Build the labelling page.
3. Label the gold set before seeing any model output.
4. Teacher labels for the training pool, with the leakage check passing.
5. Baselines: a keyword rule, and base 4B both zero-shot and few-shot.
6. LoRA training on Tinker, iterating on the dev split until improvements stop. Each iteration is recorded.
7. Eval B, ablations B1 to B10, and edge-case slices E1 to E14.
8. The failure log, and `eval/MODEL_CARD.md`.
9. The local export and the offline proof.
10. The full pass over all triaged candidates.

**Gate**
- The gold hash hasn't changed since the freeze, and the leakage check passes.
- The eval JSON and charts include confidence intervals.
- At least one failure is written up with its fix.
- The offline proof passes, and the full-pass counts are recorded.
- The EM audits 30 random reader outputs against their clippings.

### 2D: load, cluster and harvest
**Persona:** data engineer.
- Geocode, cluster, embed, and load Atlas.
- `make db-verify` runs geo, fuzzy and vector queries and checks their expected results and latencies.
- The top-case rule, and the follow-up harvest as a second Temporal pass.

**Gate**
- Atlas counts match the local counts, and storage is within the limit.
- `db-verify` passes.
- The harvest has written output for every case.

## 5. Phase 3: backend and APIs

### 3A: the investigator
**Persona:** software engineer and ML specialist.
- `InvestigateCaseWorkflow`, with Gemma 4 26B-A4B running locally as the default model and Ultramarine as the comparison run.
- Tools: archive search, death notices, SerpApi, and Wikipedia as the fallback.
- The guardrails, Sentry agent traces, and budget caps.
- Kill test 2, then 30–60 case files and eval C.

**Gate**
- Kill test 2, by the counters: no completed paid call is repeated, and any call that was in flight at the kill is counted and reported.
- 100% of the claims kept are verified, and dropped claims are logged.
- Sentry traces carry tokens and cost.
- The Ultramarine comparison records the actual cost.
- The EM audits 5 case files end to end against their clippings.

### 3B: API and static export
**Persona:** software engineer.
- FastAPI endpoints from `SRS.md` section 6, with contract tests, Sentry, the privacy tests and latency measurements.
- `export_static`, plus the cached crops for the front page and the top cases.

**Gate**
- Tests are green, and the OpenAPI document is generated.
- Latency numbers are recorded.
- The export can be reproduced.

## 6. Phase 4: frontend and integration

### 4A: brand and design system
**Persona:** UI and UX specialist.
- **`Docs/BRAND.md`:** the name, voice, nameplate, mark, colours (a table of contrast-checked pairs), type, motion, materials, and do and don't.
- **Logo set:**
  - the nameplate in UnifrakturMaguntia, as SVG outlines
  - a rubber-stamp mark for small sizes
  - the favicon set
  - a social-card template built on a real clipping
- **Category assets (SVG):**
  - outcome stamps for unexplained, explained, hoax and unknown, with an ink filter
  - eight place-type glyphs in a 19th-century atlas engraving style
  - three precision pins
  - kind tags and decade frame markers
  - the envelope, the index card, the request slip, the scissor-edge mask, and **-30-**
- **Tokens:** CSS variables for both modes, the type scale, spacing, paper shadows and motion (heavy damping, no bounce).
- **The component library,** and a style-guide route that shows every component with real archive data.
- **The Halloween look** comes from the reading room after dark, as `UI-IDEAS.md` describes, and never from costume-shop iconography.

**Gate**
- The contrast script passes.
- The EM reviews style-guide screenshots in both modes and at phone width.
- The owner is shown the brand set before the page work begins.

### 4B: pages and integration
**Persona:** UI and UX specialist, software engineer, and product manager for the feature review.
- The front page, town drawer, case page, the reel, the method page and the 404, wired to the static JSON and the live API.
- The seven signature moments with their reduced-motion fallbacks, and the map.

**Gate**
- Playwright e2e passes on phone and desktop, in both modes.
- axe and Lighthouse pass, no request goes to Google Fonts, and the copy lint passes.
- The EM walks through towns with one report, many reports and none.

### 4C: deploy (owner's yes)
- `render.yaml`, the Atlas network-access change, environment variables, Sentry releases, and a smoke test on the live URL.

### 4D: walks (owner's call)
- `SRS.md` WALK-1 to WALK-3.

## 7. Phase 5: polish and QA

### 5A: QA and hardening
**Persona:** QA engineer and DevOps engineer.
- A full test pass, a regression list and fixes.
- Performance work, and a security review (secrets, CORS, dependency audit).
- The Entire checkpoint secret scan.
- The README: reproduction steps, "What it can't do", and the failure log.
- The numbers sheet, from `make numbers`.

### 5B: launch
**Persona:** product manager.
- Screenshots, GIFs and the launch video, following `/Users/hotragn/Documents/Claude Code/tools/brag/skills/brag-slim/SKILL.md`.
- The DEV post draft, following the template:
  - every section, including The Spirit of It
  - My Agent Session, from Entire
  - the prize categories
- The EM reviews the draft against the judging rubric.
- The owner approves publishing it, and approves making the repo public for the GitHub embed.

**Final gate: the judging checklist**
- **Writing:** one strong real case carries the post. Every number appears in the numbers sheet. The voice is plain.
- **Relevance:** the theme is clear, and all four open-angle questions are answered.
- **Creativity:** the person behind the ghost, and then and now.
- **Technical execution:** both kill tests, eval B with its intervals, and 100% verified quotes.
- **Partner technology:** proof for each category listed.
- **Rules:** started and finished inside the window, prior work credited, tags `devchallenge` and `hf26challenge`.
