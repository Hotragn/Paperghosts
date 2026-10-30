# SRS: Paper Ghosts

Software requirements, each with an ID and how it is verified. The gates in `BUILD-PLAN.md` check against these IDs. The product view is in `PRD.md`, and the design is in `ARCHITECTURE.md`.

## 1. Definitions
- **Article:** one article region from AmericanStories, with its text, headline, bounding boxes and page.
- **Printing:** one article as printed in one paper on one date.
- **Story:** a cluster of printings of the same text. Syndicated stories were reprinted in many papers.
- **Candidate:** an article that hit the lexicon.
- **Report:** a candidate the reader classified as `kind = report`.
- **Case:** a report the investigator worked on.
- **Clipping:** the crop of the page scan for one article.
- **Verified quote:** a quote the verifier found in the source text, within the calibrated fuzzy threshold.
- **Precision:** how exactly a location is known: town, street or building.

## 2. Functional requirements

### 2.1 Ingest (ING)
| ID | Requirement | Verified by |
|---|---|---|
| ING-1 | All 180 year files are streamed without ever storing a tarball. Ingest outputs total at most 10 GB on disk. | Per-year manifests, and a disk-use line in eval A |
| ING-2 | Each year file is one Temporal activity, with heartbeats and a retry policy. Outputs are idempotent. | The Temporal UI history, and kill test 1 |
| ING-3 | The lexicon is versioned in code, covers common OCR variants, and each candidate records the terms it matched. | Unit tests, including OCR-variant cases |
| ING-4 | Each year records its pages, articles and candidates, by state and by term. | `eval/results/archive_read.json` |
| ING-5 | Each year writes a random non-candidate sample and a near-miss pool. | Files exist, and eval A has a recall section |
| ING-6 | The crop builder handles single-column and multi-column articles (`bbox_list`). It is checked on 50 random candidates spread across as many batches as the sample allows. | `eval/results/crop_check.json`, plus a contact sheet image |

### 2.2 Reader (RDR)
| ID | Requirement | Verified by |
|---|---|---|
| RDR-1 | The gold set has 150–300 articles, stratified by decade and term. It is frozen and hashed before training, and the split is committed. | `eval/gold/split.json` and `eval/gold/HASH`, unchanged in git history after the freeze |
| RDR-2 | The label schema covers: `kind` (report, fiction, idiom, religious, advert, other); place, people, seen and outcome (unexplained, explained, hoax, unknown); and, for walks, specific place, place type (house, church, cemetery, inn or hotel, road or bridge, public building, ship, other) and precision. Each value carries a verbatim quote. | Schema tests |
| RDR-3 | `eval/gold/POLICY.md` holds the rules for hard cases and is written before any labelling. | Git history order |
| RDR-4 | Training data is disjoint from the gold set, including reprints of gold stories. | `scripts/check_leakage.py` exits 0 |
| RDR-5 | LoRA training runs on Tinker. The configs, checkpoints and seeds are recorded. | `eval/results/reader_runs.json` |
| RDR-6 | Eval B compares base 4B, tuned 4B and the teacher on the gold set. It reports metrics with bootstrap 95% intervals, cost per 10,000 articles, and p50 and p95 latency. | `eval/results/reader_eval.json`, plus charts |
| RDR-7 | Every ablation in section 7.2 is run, or its absence is explained. | Ablation JSON and charts |
| RDR-8 | The edge-case suite in section 7.3 is reported slice by slice. | `eval/results/reader_edge_cases.json` |
| RDR-9 | The quote verifier's threshold is calibrated on the gold set. A field whose quote doesn't verify becomes "not stated". | Calibration curve, plus unit tests |
| RDR-10 | The tuned student runs locally with no network, on at least 200 articles, and its agreement with the Tinker-served outputs is reported. A guard in the runner blocks sockets, so system network settings are never touched. | `scripts/offline_proof.py` output |
| RDR-11 | The full reader pass covers every triaged candidate, and its outputs are versioned. | Counts in eval A and B |
| RDR-12 | At least one failure the eval exposed is logged, with what changed because of it. | `DECISIONS.md`, and the README failure log |

### 2.3 Places (GEO)
| ID | Requirement | Verified by |
|---|---|---|
| GEO-1 | The publication place is parsed from the LCCN title and geocoded offline against GeoNames `cities1000`. A manifest records the source, retrieval date and licence. | Parser tests on at least 200 distinct titles, plus the manifest |
| GEO-2 | Every location carries its precision and source. Street or building coordinates exist only when a source supplies them. | Schema validator, plus a test |
| GEO-3 | When a place name is ambiguous, the state from the article or the paper decides. A place that can't be resolved gets no pin and is listed. | Tests, plus an unresolved-places report |

### 2.4 Data layer (DB)
| ID | Requirement | Verified by |
|---|---|---|
| DB-1 | Collections and JSON Schema validators are generated from the Pydantic models (`ARCHITECTURE.md` section 4). | `make db-init` is idempotent |
| DB-2 | Indexes exist: 2dsphere, Atlas Search with fuzzy matching, Vector Search, and compound indexes. | `make db-verify` |
| DB-3 | Storage stays within the cluster limit, and what stays local is documented. | A storage report in eval A |
| DB-4 | Printings are clustered into stories, and the cluster precision is measured on a labelled sample of at least 100 pairs. | `eval/results/clustering.json` |
| DB-5 | The loader upserts by stable IDs, so re-running it changes nothing. | Integration test |
| DB-6 | Geo, fuzzy and vector queries return the expected results, and their latencies are recorded. Example: a search for "appariiion" finds "apparition". | `make db-verify` output |

### 2.5 Investigator (INV)
| ID | Requirement | Verified by |
|---|---|---|
| INV-1 | The rule that picks the top cases is written down and versioned. | The code, plus `DECISIONS.md` |
| INV-2 | The follow-up harvest runs on Temporal and streams each needed year file once. | Workflow history, plus manifests |
| INV-3 | Every model call and every tool call is an activity with an idempotency key and a budget cap. | Code review, plus workflow history |
| INV-4 | A claim is kept only if its citations verify. Dropped claims are logged with the reason. | Each case's `drops` log, plus an audit |
| INV-5 | A person link shows both clippings, a grade and its reasons. No cause of death is stated beyond what was printed. | An audit of every person link |
| INV-6 | Each "now" item comes from SerpApi, or from Wikipedia with a label saying so, and carries its URL and retrieval date. A difference is recorded only when both quotes exist. | Schema, plus an audit |
| INV-7 | Kill test 2: the worker is killed mid-investigation, and the workflow resumes at the same step. No completed paid call is repeated. A call that was in flight at the moment of the kill is retried, and the test reports how many there were. | Temporal UI screenshots, plus call counters from the providers and from activity logs |
| INV-8 | Each case run produces one Sentry trace, with spans for model calls carrying model, tokens, cost and latency. | Trace links, plus numbers pulled with `SENTRY_AUTH_TOKEN` |
| INV-9 | Ultramarine runs on the same cases as the default model, and its actual cost is recorded. | `eval/results/investigator_compare.json` |
| INV-10 | Eval C counts case files, named deaths, cases explained or exposed, and then-and-now differences. | `eval/results/investigations.json` |

### 2.6 API (API)
| ID | Requirement | Verified by |
|---|---|---|
| API-1 | The endpoints in section 6 are implemented with input validation, pagination and a consistent error format. | Contract tests |
| API-2 | `/api/near` rounds coordinates to 2 decimal places, never logs them, and keeps them out of Sentry. | A test with a log-capture fixture |
| API-3 | CORS allows only the site's own origins. Responses carry cache headers. | Tests |
| API-4 | `/api/health` reports whether Atlas is reachable. Sentry is wired up with no PII. | Test, plus a Sentry event |
| API-5 | p95 latency is measured for every endpoint against Atlas. | `eval/results/api_latency.json` |

### 2.7 Web (WEB)
| ID | Requirement | Verified by |
|---|---|---|
| WEB-1 | The pages are: front page, town drawer, case, the reel, the method page, a 404 ("This page was never filed."), and walks if they are built. | Playwright e2e |
| WEB-2 | The design system covers tokens, type, components and brand assets (`BUILD-PLAN.md`, Phase 4A). A style-guide route shows every component, using real archive data only. | Screenshots of the style guide in both modes and at phone width |
| WEB-3 | The pull-chain switches lights on and off. The default follows the device setting and the time. | e2e |
| WEB-4 | The seven signature moments from `UI-IDEAS.md` are built, each with its reduced-motion fallback. | e2e with reduced motion emulated |
| WEB-5 | Layouts are phone-first, and clipping crops are lazy-loaded. The first clipping is the LCP element. | Lighthouse |
| WEB-6 | Each clipping's alt text is its transcription. | e2e |
| WEB-7 | UI copy follows the voice rules, and a lint script fails the build on banned words. | `make lint` |
| WEB-8 | Fonts are self-hosted, so no request goes to Google. | The e2e network log |
| WEB-9 | The map uses MapLibre with OpenFreeMap tiles and a muted atlas style. Pins show precision: a ring for a town, a line for a street, a square for a building. | Screenshot, plus a unit test of the pin choice |
| WEB-10 | Every data view has loading, empty and error states. A sleeping API changes only the live features. | e2e with the API stubbed down |

### 2.8 Walks (WALK, P2)
| ID | Requirement | Verified by |
|---|---|---|
| WALK-1 | A walk has at least 3 public stops, located at street or building precision, all within about 3 km. A private home is never a stop. | Generator tests |
| WALK-2 | Whether each stop still stands is checked through SerpApi Maps, and only checked stops are counted. | Eval D counts |
| WALK-3 | The assignment sheet prints cleanly and works offline. | A print-to-PDF snapshot |

## 3. Non-functional requirements
| ID | Requirement | Verified by |
|---|---|---|
| NFR-SEC-1 | No secret appears in the repo, in logs, or in recorded sessions. A secret scanner runs in CI, and the Entire checkpoints are scanned before the repo goes public. | CI, plus a scan report |
| NFR-SEC-2 | API input validation, a simple rate limit, and a dependency audit. | Tests, plus an audit report |
| NFR-PRIV-1 | No accounts, no tracking analytics and no session replay. The only thing stored on the device is the lights preference. | Code review, plus the e2e network log |
| NFR-REL-1 | The ingest and the investigation both survive a killed worker (kill tests 1 and 2). | Screenshots, plus counters |
| NFR-PERF-1 | Core Web Vitals are "good" on a mid-range phone profile. Initial JS stays under 200 KB gzipped, with the map loaded lazily. | Lighthouse, plus a bundle report |
| NFR-A11Y-1 | WCAG 2.2 AA: reading-text contrast of at least 4.5:1 in both modes, a visible blue-pencil focus style, full keyboard use, reduced motion respected, semantic headings. | axe, a contrast script, plus a keyboard e2e test |
| NFR-REPRO-1 | Every number shown anywhere comes from a script. `make numbers` regenerates the numbers sheet, with the command behind each number. | The numbers sheet diffs clean |
| NFR-COST-1 | Only free tiers and existing credits are used. Every run logs its cost. SerpApi use stays within budget. | Cost logs |
| NFR-OBS-1 | Both Sentry projects receive events, and releases are tagged with the git SHA. | The Sentry API |
| NFR-TEST-1 | Unit tests (lexicon, crop URLs, quote verifier, geocoder, schemas), integration tests (Temporal test environment), contract tests (API) and e2e tests (Playwright) all run from `make test`. | CI |
| NFR-LIC-1 | AmericanStories (CC-BY-4.0), GeoNames (CC-BY), the LoC scans, the OpenStreetMap and OpenFreeMap attribution, the font licences and the React Bits licence are all credited on the method page and in the README. | Review |

## 4. Constraints
- **Machine:** Apple M4 with 10 cores, 24 GB of RAM, and about 35 GB of free disk (measured Oct 29). No Docker.
- **Installed tools:** `uv`, Node and `pnpm`, the Temporal CLI with its dev server, Ollama (with `gemma4:26b-a4b-it-qat` and smaller Gemma 4 variants already pulled), `gh` and `entire`. Nothing is installed globally; project dependencies go through `uv` and `pnpm`.
- **Keys:** `.env` holds them; check them by shape only. The names are listed in `BRIEF.md`; the Ultramarine key is `PAPERINSTRUMENTS_API_KEY`. `GEMINI_API_KEY`, `ELEVENLABS_API_KEY` and `TABPFN_TOKEN` are present but unused.
- **Atlas:** the existing cluster. Its tier and storage limit are recorded in Phase 1.

## 5. Data requirements
- **Schemas:** `ARCHITECTURE.md` section 4. Pydantic is the source; Atlas validators are generated from it.
- **Stable IDs:**
  - A report is `r_` plus its primary article ID.
  - A case is `c_` plus its report ID.
  - A place is its GeoNames ID.
- **Every derived record** carries the versions that made it (lexicon, prompt, model or adapter, code SHA).
- **Dates** are ISO 8601. `month_day` is `MM-DD`, used by "Printed on this night".
- **Text:** the OCR text is stored as printed and is never corrected in place. A cleaned transcription, if one is shown, is stored separately and labelled.

## 6. API contract (read-only)
| Method and path | Returns |
|---|---|
| `GET /api/health` | `{ok, atlas, version}` |
| `GET /api/places?q=&state=` | Matching towns: `{place_id, name, state, report_count, years}` |
| `GET /api/towns/{place_id}` | The drawer: the place, its count line, and its reports `{id, date, paper, label, outcome, precision, location}` |
| `GET /api/reports/{id}` | The full case page payload: the report, plus its case if one exists |
| `GET /api/search?q=&state=&decade=&page=` | Text-search hits with a snippet, and the misread spellings each hit matched, e.g. `{scanned: "appariiion", term: "apparition"}` |
| `GET /api/near?lat=&lon=&km=` | Reports near a rounded point. The coordinates are never logged. |
| `GET /api/reports/{id}/similar?k=` | Vector-search neighbours |
| `GET /api/tonight?md=MM-DD` | Reports printed on that month and day |
| `GET /api/stats/reel` | Per-year and per-state series |
| `GET /api/walks/{place_id}` | A walk (P2 only) |

Errors take the form `{"error": {"code", "message"}}`. The core path is mirrored as static JSON (`ARCHITECTURE.md` section 3.6), so the site works while the API sleeps.

## 7. Evaluation specifications
Results are saved as JSON plus a chart under `eval/results/`, and each is produced by one command.

### 7.1 Evals A to D
- **A, the archive read:**
  - pages and articles read, and candidates per year
  - reports per million articles, by year and by state
  - the term mix and an OCR-quality distribution
  - prefilter recall: a random-sample upper bound (rule of three when no misses are found) and the misses found in the near-miss pool, with the lexicon changes they caused
- **B, the reader:**
  - kind accuracy and macro-F1, and report precision, recall and F1
  - field match rates, and the share of quotes verified
  - the hallucinated-quote rate
  - cost per 10,000 articles and latency
  - bootstrap 95% intervals throughout
  - the headline is the accuracy gap and the cost per 10,000 articles
- **C, the investigations:** case files written, named deaths found, cases explained or exposed, then-and-now differences, the claim-verification rate and dropped claims, and Gemma against Ultramarine on the same cases (claims, verification rate, cost, latency).
- **D, the app:** Lighthouse on mobile, axe, contrast, e2e on phone and desktop in both modes, and the walks counts if walks are built.

### 7.2 Reader ablations
| ID | What changes | Why it matters |
|---|---|---|
| B1 | Base 4B, tuned 4B, teacher | The headline comparison |
| B2 | Training set size (a learning curve of at least 3 points) | Whether more teacher labels would help |
| B3 | LoRA rank and learning rate (a small grid, within credits) | Picks the trained model |
| B4 | Output format: fields with quotes against kind only | The cost of grounding |
| B5 | Quote verifier on and off, plus a threshold sweep | Precision of the fields shown |
| B6 | Triage on and off | Reports lost against cost saved |
| B7 | Slices by OCR quality | Robustness to rough scans |
| B8 | Slices by decade | Language drift from 1774 to 1963 |
| B9 | Base 4B zero-shot against few-shot | Makes the baseline fair |
| B10 | Reprint leakage removed, or not | Proves the scores aren't inflated |

Model selection uses a dev split. The gold set is used only for these final runs.

### 7.3 Edge-case suite
Each slice uses at least 5 gold items where the archive has them:
- E1: sermons and hymns about the Holy Ghost
- E2: idioms ("ghost of a chance", "gave up the ghost", "not the ghost of a")
- E3: ghost stories as fiction, serials and Christmas stories
- E4: theatre and illusion adverts (Pepper's ghost), patent medicine and real estate
- E5: spiritualist séances and rappings (`POLICY.md` decides their kind)
- E6: hoax exposures and pranksters caught
- E7: humour and joke columns
- E8: phantom ships, trains and lights
- E9: one story reprinted under different datelines
- E10: badly garbled OCR
- E11: segmentation errors, where several items are merged into one article
- E12: non-English text
- E13: "Ghost" as a surname or a place name
- E14: political figures of speech ("the ghost of the tariff")

## 8. Traceability
| Requirements | Phase | Evidence |
|---|---|---|
| Environment, CI, skeleton | 1 | `eval/results/phase1_env.json`, CI run, skeleton screenshot |
| ING-*, eval A | 2A | `eval/results/archive_read.json`, kill test 1, crop check |
| GEO-*, DB-1 to DB-3 | 2B | `make db-init`, storage report, parser tests |
| RDR-*, eval B | 2C | `eval/results/reader_*.json`, `eval/MODEL_CARD.md` |
| DB-4 to DB-6, INV-2 | 2D | `make db-verify`, `eval/results/clustering.json`, harvest manifests |
| INV-*, eval C | 3A | Case files, kill test 2, Sentry traces |
| API-* | 3B | Contract tests, `eval/results/api_latency.json` |
| WEB-*, NFR-A11Y, NFR-PERF | 4 | e2e, axe, Lighthouse, screenshots |
| NFR-*, the numbers sheet, launch | 5 | `make numbers`, README, scan report, the post draft |
