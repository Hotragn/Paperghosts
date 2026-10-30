# Product brief: Paper Ghosts

A newspaper's archive of old clippings is called its morgue. Paper Ghosts is a morgue for every ghost that America's newspapers reported between 1774 and 1963.

## What it is
You type a town and get the real ghost reports printed in or about that town. They come straight from old newspapers, not from legends retold on the web. Each report shows:
- **the original clipping**, cropped from the Library of Congress page scan, next to its transcription
- the paper, date and place, plus who saw what and where
- **what happened next**: follow-up stories, the debunking, the arrest of the prankster, the family that moved out
- **the person behind the ghost**, when a name leads to a real death notice or inquest in the same papers
- **then and now**: what the 1890s paper said, next to what today's web and ghost tours say about the same place

The site never writes a ghost story. Everything it shows was printed in a newspaper, and every claim links to the clipping it came from.

**Walks: an optional layer, built only after the core works.** Search stays the front door. On top of it:
- **Near me:** a map of reports around you. Your location is rounded to about 1 km, used for that one query and never logged.
- **Self-guided walks:** offered only where a town has at least 3 precisely located stops that the public can see from a street, all within about 3 km.
  - Each stop shows its clipping, what happened next, and what stands there now.
  - A walk can be saved as a printable page, so it works offline.
- **Road trips** across several towns: a stretch goal, and the first thing to cut.

## Who it's for
Anyone curious about their own town on Halloween, plus local historians, genealogists and ghost-tour guides who want the original source rather than the retelling.

## Non-negotiables
1. **Secrets:**
   - Keys live in `.env`. Never print, log, echo or commit them; read them through the environment only.
   - `.env` is already at the repo root, and `.gitignore` covers it. It holds `TINKER_API_KEY`, `MONGODB_URI` and `RENDER_API_KEY`, plus a few unused keys.
   - For Sentry it holds `SENTRY_DSN` (API project), `SENTRY_DSN_WEB` (web project), and `SENTRY_AUTH_TOKEN` with `SENTRY_ORG` and `SENTRY_PROJECT`. The token can read events and traces, and write projects.
   - Optional keys the owner may fill in later: `SERPAPI_API_KEY`, `ULTRAMARINE_API_KEY` (with `ULTRAMARINE_BASE_URL` and `ULTRAMARINE_MODEL`), and `HF_TOKEN`. An empty value means the service isn't set up. Nothing in the build may wait on them.
   - Check every key by shape only (prefix, length, a test call), never by printing it.
2. **No fake anything:**
   - No invented results, users, quotes or numbers.
   - Every number in the README, results files or UI must come from a script in this repo and be reproducible with one command.
   - Approximations are labelled as approximations where they appear.
3. **Sources, not stories:**
   - The model only reads, classifies and quotes.
   - Every extracted field carries a verbatim quote from the article. Code checks the quote against the source text, with fuzzy matching for OCR noise.
   - A field without a verified quote shows as "not stated", never as a guess.
   - No generated fiction anywhere in the product.
4. **Respect the dead:**
   - These were real people. No mockery, and no guessing at causes of death beyond what the papers printed.
   - When the investigator links a ghost to a death, it shows both clippings and states how sure the link is.
   - Walks never send anyone onto private property. A private home is never a stop.
   - Every pin says how precise its location is: town, street or building.
5. **Quality bar:**
   - Premium and restrained, with real typography. The visual direction comes from the owner's `Docs/UI-IDEAS.md`, and the real scans are the only imagery.
   - No Halloween clip art, no emoji soup, no generic gradient "AI app" look, no filler copy.
   - Fast on a phone: lazy-load the clipping images.
6. **Honest limits are written down:** the README gets a "What it can't do" section, plus a log of failures found.
7. **Anything public waits for the owner's yes.** Stop and ask before any of these:
   - making the repo public
   - deploying under the owner's accounts
   - pointing the domain
   - posting anywhere or messaging anyone
   - spending money beyond free tiers and existing credits
8. **Start fresh.** Don't copy code from `week2/` or `week3/`. Reading them for patterns is fine.

## Data (verified 2026-10-29)
**AmericanStories** (Hugging Face `dell-research-harvard/AmericanStories`, CC-BY-4.0, from Harvard's Dell Research): article-level text extracted from the Library of Congress's Chronicling America scans.
- **Files:** 180 per-year files, `faro_{year}.tar.gz`, 340 GB in total.
  - Download: `https://huggingface.co/datasets/dell-research-harvard/AmericanStories/resolve/main/faro_{year}.tar.gz`
  - Sizes: 1850 is 0.99 GB; 1897–1920 are 6–7.6 GB each.
- **Format:** each tar member is one page scan, as JSON:
  - `lccn`: `{title, state, lccn, …}`, where `title` includes the place of publication, e.g. "The New York herald. [volume] (New York [N.Y.]) 1840-1920"
  - `edition`: `{date}`
  - `scan`: `{width, height, raw_data_loc}`
  - `full articles`: a list of `{headline, article, byline, bbox, bbox_list, id, full_article_id}`
- **Machine limits:**
  - Download speed measured 66 MB/s, so a full pass is about 1.5 h of transfer.
  - Only **37 GB of disk is free**. Stream every file and never store the tarballs.
- **First probe (1850):** 733,880 articles, 1,018 mentioning ghosts and 33 strong reports, among them the Phelps family "knockings" in Stratford, Conn. The OCR is rough in places.

**Page scans for the clippings** (public domain, Library of Congress IIIF image service):
- `raw_data_loc` looks like `https://chroniclingamerica.loc.gov/data/batches/{batch}/data/{lccn}/{reel}/{issue}/{seq}.jp2`.
- The crop is `https://tile.loc.gov/image-services/iiif/service:ndnp:{awardee}:batch_{batch}:data:{lccn}:{reel}:{issue}:{seq}/{x},{y},{w},{h}/pct:50/0/default.jpg`, where:
  - `awardee` is the first part of the batch name (`dlc_marcus_ver01` gives `dlc`)
  - `bbox` is `[x1, y1, x2, y2]` in scan pixels, so `w = x2-x1` and `h = y2-y1`
- This was verified on one 1850 New York Herald article, and the crop matched the text. Verify it across many batches before relying on it.
- Use `bbox_list` for articles that run across columns.

**Gone:** the old Chronicling America JSON API returns 404, so the dataset above is the source.

**Places:** take the publication place from the `lccn` title, plus places named in the article. Geocode offline with GeoNames (`cities1000`, CC-BY), recording the source and retrieval date in a manifest.

## Stack (each tool has a real job, and each job needs proof: a screenshot, a number, or a failure it caught)
**Tinker is the main tool, and the depth goes there.** The others support it with one job each. The data layer is MongoDB Atlas (already set up), not Tiger Data. There is no .tech domain.
- **Temporal:** durable runs. The 340 GB ingest is one workflow, with one activity per year file, heartbeats and retries. Investigations are workflows too, with retries on flaky tool calls.
  - Run Temporal locally with the CLI dev server.
  - Prove it twice, and capture the Temporal UI timeline both times:
    - Kill the worker mid-ingest.
    - Kill it mid-investigation. The investigator agent must resume at the same step without repeating paid model calls it already made.
  - The investigation is the main Temporal story: an agent whose every model call and tool call is a retried, resumable step.
- **Tinker:** the reader, a small model trained for this task.
  - A large teacher (Qwen3.5-397B, or the best available) labels candidate articles.
  - A small student (Qwen3.5-4B, LoRA) learns from those labels.
  - Measure the base student, the tuned student and the teacher on a held-out gold set: accuracy, cost per 10,000 articles and latency.
  - The tuned student is the model that reads the whole archive, and it must also run locally offline.
  - Record at least one failure the eval exposed and what changed because of it. For example, sermons about the Holy Ghost might be read as sightings.
- **MongoDB Atlas:** the data layer.
  - Geo queries for "near this town" and "near me", and for building walks.
  - Atlas Search with fuzzy matching, because OCR turns "apparition" into "appariiion".
  - Atlas Vector Search for "ghosts like this one", with an open embedding model.
  - The investigators' case files.
  - Check the cluster's storage limit first, and keep the bulk candidate files local if it is small.
- **The investigator:** for each top case, it works through a pile of related old articles (follow-ups, death notices, inquests, debunkings) and writes a case file in which every claim cites a clipping.
  - By default it runs on an open-weight model (local Gemma 4 26B through Ollama, or the Tinker teacher), so nothing waits on a new account.
  - When an Ultramarine key exists (Paper Instruments' model, called through the OpenAI or Anthropic SDK), run the same cases on it, compare the case files, and record what each run actually cost.
- **SerpApi (when its key exists):** live web search for the investigator. Is the house still standing, and what do today's legend and ghost tours claim? This produces the then-and-now cards.
  - The free plan is 250 searches a month, so budget them.
  - Until the key exists, use Wikipedia's public API for the "now" side, and say so on the card.
  - For walk stops, use its Google Maps results to check whether the place still stands, and to get its coordinates and opening hours.
- **Sentry:** traces of investigator and reader runs, covering latency, tokens and cost per case.
  - Two projects already exist in org `hotragn`: `paperghosts-api` (Python, FastAPI) and `paperghosts-web` (React).
  - Sentry is linked to the GitHub repo `Hotragn/Paperghosts`, so releases and suspect commits can work.
  - Use `SENTRY_AUTH_TOKEN` to pull real trace numbers for the write-up. Keep only the traces that explain a real bug or bottleneck, and write up that story in `DECISIONS.md`.
- **Render:** hosts the site and the API. The owner approves the deploy.
- **Optional, only if time allows and it does real work:**
  - Entire, to capture the agent sessions behind the build. It's already enabled in this repo, so every build session is recorded. Before the repo goes public, scan the recorded sessions for secrets.
  - Gemma, to re-read the scan image when the OCR is unreadable.
  - Backboard, to compare open models through one key before training.

## Depth requirements (each has an eval or test, saved under `eval/results/` as JSON plus a chart)
**A. Archive read.**
- Total pages and articles read, candidates per year, and ghost reports per million articles by year and by state.
- Recall of the prefilter, measured on a random sample of non-candidates.

**B. Reader.**
- **Gold set:** 150–300 articles stratified by decade and by lexicon term, frozen before any training, with the split committed alongside its hash.
- **Who labelled the gold set:** the build agent labels it before seeing any model's output. It reads the OCR, and the scan crop wherever the OCR is unclear. The README says so plainly. If the owner later re-checks a sample in a small labelling page, report how often the two agree.
- **Labels:**
  - `kind`: one of report, fiction, idiom, religious, advert or other
  - plus place, people named, what was seen, and outcome (unexplained, explained, hoax or unknown), each with a quote
  - for Walks:
    - the most specific place named (a building, street or landmark), with its quote
    - its type: house, church, cemetery, inn or hotel, road or bridge, public building, ship, or other
    - how precise it is: town, street or building
- **Compare** base 4B, tuned 4B and the teacher. The headline is the accuracy gap and the cost per 10,000 articles.

**C. Investigations.**
- Case files for the top 30–60 cases.
- A count of how many led to a named death and how many were explained or exposed.
- Then-and-now differences, such as a legend that adds a murder the original report never mentioned. Count only what is actually found.

**D. App.**
- Town search, a map, a case page and an archive chart.
- Works on a phone, and in light and dark ("lights off") modes.
- If Walks is built, report how many towns qualify for a walk and how many stops were confirmed still standing. Count only what was checked.

## Repo hygiene
- The repo is the **private** GitHub repo `Hotragn/Paperghosts`, already cloned here. Planning docs live in `Docs/`, and `Docs/IDEAS.md` stays out of git.
- Small, clear commits.
- `make setup`, `make ingest`, `make eval` and `make app` (or equivalents), plus a `README.md` with reproduction steps.
- `DECISIONS.md` (numbered decisions with the reason) and `RESUME.md` (current status, numbers, risks, next step).
- Ship a complete, honest vertical slice first, then deepen.
- The site must be live before Halloween (Oct 31). Plan the steps around that date.

## Steps (do only the step you are asked for, and end each with a STATUS block in RESUME.md)
1. **Setup and archive read:**
   - Environment, keys check (shape only), Temporal dev server.
   - Entire session capture is already enabled in this repo (Claude Code hooks, telemetry off). Confirm it with `entire status`, and don't re-enable or reinstall it.
   - The ingest workflow over all 180 year files, with candidates and per-year counts stored locally.
   - The kill-the-worker test.
   - The crop check on 50 random candidates across batches.
   - Tinker balance and model list. MongoDB Atlas tier and storage limit.
2. **Reader:** gold set and labelling page, teacher labels, LoRA training on Tinker, eval B, local export, then the tuned reader over all candidates.
3. **Data layer:** reports into Atlas (geo, fuzzy search, vectors). A second Temporal pass that pulls follow-ups and death notices for the top cases.
4. **Investigator:** an open-weight model plus archive search (and Ultramarine and SerpApi once their keys exist), durable on Temporal, traced in Sentry, then eval C.
5. **App:** the site, and a deploy on Render once the owner says yes.
   - Before designing anything, read the owner's UI ideas in `Docs/UI-IDEAS.md`. Follow them wherever they don't conflict with the non-negotiables.
   - Then Walks, but only if Steps 1–4 are done by Oct 30, 22:00 UTC. Otherwise cut it and say so in RESUME.md.
6. **Hardening and launch assets:**
   - Tests, README, and a numbers sheet listing every headline number with the command that produced it.
   - Captioned screenshots, short GIFs, and a launch video following `/Users/hotragn/Documents/Claude Code/tools/brag/skills/brag-slim/SKILL.md`. Read that skill and follow it; don't install anything globally.
