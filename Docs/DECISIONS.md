# Decisions

Numbered, each with its reason. Newest at the bottom.

## Before Step 1 (2026-10-29)

**1. The source is AmericanStories, not the Chronicling America API.**
The old Chronicling America JSON API returns 404. AmericanStories has the same scans as structured article text, under CC-BY-4.0. It also keeps each article's bounding box, which lets the site crop the original clipping from the Library of Congress image service.

**2. Read the whole archive (180 year files), not a sample.**
A full pass is 340 GB. At the measured 66 MB/s that is about 1.5 h of transfer, which is affordable. Full coverage makes the counts honest and lets every US town get its results.

**3. Stream every file and never keep the tarballs.**
The disk has 37 GB free, and the largest year alone is 7.6 GB.

**4. Walks is an optional layer on top of search, and it is built last.**
Halloween and Día de los Muertos are nights when people go out, both to haunted places and to graves. On Oct 29, none of 598 posts offered walks built from original sources. The nearest were GeoLetter (letters left at places) and Trailhead (general outing cards).
Walks also gives two tools a real job:
- SerpApi's Google Maps results answer "is it still standing?"
- Atlas geo queries answer "near me".

Old reports are often vague, and many of the places are gone. So walks use only precisely located public stops, every pin shows how precise it is, and Walks is cut if Steps 1–4 run late.

**5. One main tool (Tinker); the others support it. MongoDB Atlas, not Tiger Data. No .tech domain.**
Week 2's partner winners each made one partner the core of the product and proved it under failure. Our Week 2 entry, Cubby, spread thin uses across seven partners and won nothing. So the depth goes into the Tinker reader, and Atlas, Temporal, Render and Sentry each get one real job.

Why Atlas over Tiger Data:
- Atlas is already set up; Tiger Data would need a new account.
- Articles are JSON documents, and Atlas covers all three searches we need (geo, fuzzy text, vectors) in one place.
- On Oct 29, three entries claimed Tiger Data, including Still Here by the author who won Tiger Data in Week 1.

The owner chose not to use a .tech domain.

## Planning (2026-10-29)

**6. The build runs in five phases with gates, managed by an EM session.**
`BUILD-PLAN.md` maps the `BRIEF.md` steps onto five phases: scaffolding; database, schemas and data models; backend and APIs; frontend; polish and QA. Each milestone ends at a gate the EM checks before the next one starts. The owner manages the schedule, so whether Walks is built is the owner's call at the Phase 4 gate.

**7. Static-first site: the core path is prebuilt JSON, and the live API handles search, near me and similar.**
Free Render web services sleep after a short idle. A judge's first click has to be instant, and an outage at the API, at Atlas or at LoC shouldn't blank the front page, a town or a case.

**8. Stories and printings are counted separately.**
Syndicated ghost stories were reprinted in many papers. Counting each printing as its own ghost would inflate the numbers and duplicate cases. Reprints of a gold article in the training data would also inflate the reader's scores.

**9. Models are selected on a dev split, and the gold set is used only for final evals.**
That keeps the held-out numbers honest.

**10. The investigator's default model is Gemma 4 26B-A4B (QAT), running locally through Ollama. Ultramarine is the comparison run.**
The model is already on this machine (15 GB), it's open-weight, and it keeps the investigation offline. Both runs work the same cases, so the comparison is fair.

**11. The Halloween look comes from the reading room after dark.**
`UI-IDEAS.md` sets the direction: the lamp, the lights off, and the scans as the only imagery. Costume-shop iconography is out.

**12. Config accepts both names for the Ultramarine key.**
`.env` names it `PAPERINSTRUMENTS_API_KEY`, while `BRIEF.md` says `ULTRAMARINE_API_KEY`. The owner's file stays as it is.

## Phase 1 (2026-10-29)

**13. `make keys` checks each key with the service's cheapest read, and never prints a value.**
- Tinker: the route the Tinker CLI's login uses to check a key. A plain HTTP call skips the SDK's 2.5 s import and its session, so the SDK arrives later, with the Tinker facts.
- Atlas: `connectionStatus`, which proves the connection is authenticated, not just reachable.
- Sentry: the auth token reads the project. A DSN can prove itself only by sending an event, so here it gets a shape check, and `phase1_env` sends the test event.
- SerpApi's account endpoint uses no searches, and Ultramarine's model list costs nothing.
- Output is fixed text, status codes and exception type names. Library messages can quote a key, URL or URI, so they never appear. A test plants canary values and fails if any 6-character slice of one reaches stdout, stderr or an exception message.

**14. Per-year counts are committed.**
`data/` stays local except `data/manifests/` and `data/counts/`. The counts are small JSON files, and keeping them in git lets Phase 2A diff a reproduced run against the committed one.

**15. Sentry collects nothing about people, and nothing a local variable holds.**
- sentry-sdk 2.73 deprecates `send_default_pii`, so `init_sentry` sets `data_collection` instead. Fields left out of it default to on, so every one this stack touches is set off: user info, cookies, request headers and bodies, query parameters, model inputs and outputs, Mongo query data and stack-frame variables. Mongo queries can carry near-me coordinates, and locals can hold keys and URIs.
- `server_name` is the component, because the default is the host name, which can name its owner.
- A `before_send` hook also strips query strings and coordinate fields from every event and transaction.
- The API and the pipeline share `paperghosts-api`, told apart by `environment`.

**16. The smoke activity resumes after its last heartbeat.**
Its first attempt fails on purpose halfway through, and the retry carries on after the failed attempt's last heartbeat. That shows heartbeats reach the server, not only that the activity sends them. The test runs in Temporal's test environment on the installed CLI, so nothing is downloaded locally.

**17. The environment facts measure the download and the parse in one pass, in two processes.**
The download runs in its own process and hands chunks to the parser, which counts only its own CPU time. In one process, the CPU-bound parser would hold the GIL and slow the very socket reads it is measured against. A fact the script can't measure is `null` with its reason, never a guess.

**18. Crops use the scan's own pixels, and loc.gov names the batch when the record doesn't.**
- One IIIF crop covers every box in `bbox_list`, in the scan's pixel coordinates, at half size.
- 9 of the 20 matching 1850 pages have no `raw_data_loc`, and their size is marked approximate. On the Lewistown page the record says 5867 × 8352 while the JP2 is 6337 × 8901: the "approximate" size is just the extent of the boxes, which are already in the JP2's pixels. The crop matched its text from the first line to the last.
- For those pages, loc.gov's item JSON names the page's IIIF service, and so its batch. Phase 2A's crop check needs that lookup, or a reel-to-batch table, for every page without `raw_data_loc`.

## Phase 2A (2026-10-29)

**19. Lexicon v1 counts the 1850s spirit noises as ghost terms, and reads through common OCR damage.**
- Only 3 of the 20 Stratford knockings articles of 1850 use a classic ghost word, and the walking skeleton's article uses none. So "knockings", "rappings" and "rappers" are ghost terms. A single "knocking", "spirits" and "strange noises" put an article in the near-miss pool instead.
- Each pattern takes the usual misreadings (long s as f, h as b or li, o as c or 0, t as l or 1, n as u), a lost i, and a word broken across a line with or without a hyphen. "spook" takes no c, because "spcck" is nearly always a misread speck.
- Recall comes first. On faro_1850, v1 keeps 2,954 of 733,880 articles (`scripts/prefilter_year.py 1850`), and 18 of the 20 known knockings articles; the other 2 are in the near-miss pool.

**20. The knocking term stays: on its own it keeps 293 candidates of 1850, and 11 of the 18 known knockings articles.**
- A bare "knocking" was never a ghost term; it only marks a near-miss. The term is the plural "knockings", with its misreadings and line breaks (263 of the 293), and phrases such as "mysterious knocking" (30).
- Read in context, all 20 of a seeded sample of the 293 are about the spirit knockings: reports, debunkings, and two theatre bills. None is about a door or a fight.
- Without the term, 7 of the 18 known articles would survive. Later decades may use "knockings" for other things, and each year's samples will show it.

**21. The prefilter pre-checks folded stems, and keeps a 2,000-article sample of each pool per year.**
- Folding the OCR classes to one letter lets 34 short stems stand for every pattern, and an article holding none of them skips the regex. Over faro_1850 the pre-check changes no article's terms (`scripts/verify_precheck.py 1850`), and the year takes 46 s instead of 98 s.
- The near-miss pool and all non-candidates are each kept as a seeded reservoir of 2,000 articles per year, in `data/samples/{year}.jsonl.zst`: 4.8 MB for 1850.

**22. The ingest runs each year in a fresh process, and a year is done once its manifest is written.**
- A year's prefilter is CPU-bound Python, so four years in one process would share a core under the GIL. The worker runs the year activity in a pool of four processes, a fresh one for each year, which also gives every year its own peak memory.
- Outputs go to partial files that are renamed once complete, and the manifest is written last. A year is skipped when its manifest's lexicon and code versions match the current ones. The code version is a hash of the modules that shape the outputs, so a docs commit doesn't re-run the archive.
- A year that fails all five attempts is listed with its reason, and the other years carry on.
- 1804, 1850 and 1910 took 2.7 s, 50.6 s and 389.4 s, wrote 39 MB in all, and peaked at 536 MB of memory (1910). A second run of 1850 wrote byte-identical counts. The code version hashes exact bytes, so even a reformat re-runs a year: format before an ingest.

**23. A year is skipped only while its cache key and every output's hash match, and a lost attempt stops at its next heartbeat.**
- The cache key is the dataset revision, the lexicon version and the code version. The ingest reads AmericanStories at its 2025-03-26 commit, `77e27fa6`, instead of `main`, so a cached year's input can't change under it.
- Manifests and counts are in git, but candidates and samples are not, so a fresh clone skipped every year and had no candidates. Each manifest now records every output's sha256, and a year is skipped only when every output on disk matches. A size check would miss a damaged file.
- The tarballs are never cached (decision 3): 340 GB won't fit on the disk, and a full re-read costs about 75 minutes and nothing else.
- Two attempts at one year can run at once. A timed-out attempt keeps going after Temporal starts its retry, and a spawn-pool child outlives a worker killed with SIGKILL and still writes its files. So partial files are named for their process, and an attempt stops at its next heartbeat (every 200 pages), before it writes anything, once it is cancelled or its parent process has changed.
- In the tests, a cancel reaches a year only through `is_cancelled()`, as in the process pool. Otherwise the SDK would interrupt the test's thread for it.
- The code is frozen while the full archive runs. The lexicon, prefilter, stream and year modules make up the code version, and a restarted worker replays the workflow's history against the workflow code.

**24. Temporal identities name the process and its role, not the host.**
The SDK's default identity is `pid@hostname`, and Temporal keeps it in every workflow's history, which the kill test's screenshots show. Like Sentry's `server_name` (decision 15), the worker, `make ingest` and `make smoke` use `pid@paperghosts-{role}` instead.

**25. The full read ran four years at a time, each on one CPU-bound core. A re-read can set its concurrency from these numbers.**
- All 180 year files, 340.4 GB at revision `77e27fa6`, took 118.6 min on 2026-10-30: an aggregate 47.8 MB/s. Every manifest's `bytes_read` equals the listed size, no year failed, and no partial file was left.
- 370,313,913 articles gave 1,050,459 candidates. The outputs take 1.94 GB (candidates 1.34 GB, samples 0.59 GB), and the highest peak memory was 535 MB (1910).
- Each year process is CPU-bound on one core: 12.8 MB/s at the median over the 87 years above 1 GB, with a range of 11.0–15.6. With four running, the network carried 55 MB/s at the median of minute samples (50–57 for the middle 80%), and 43% of the CPU stayed idle (35–45%). Alone, a year runs nearly twice as fast: 1850 took 46.8 s by itself and 85.7 s beside three others.
- Concurrency stayed at four:
  - Time isn't the constraint.
  - One clean run gives one wall time and clean kill-test evidence.
  - Eight CPU-bound processes would saturate the owner's laptop while they use it, for well short of 2×, because 6 of its 10 cores are efficiency cores.
- Six years ran twice:
  - The streams for 1872 and 1889 ended partway through a page (`tarfile.ReadError: unexpected end of data`).
  - Kill test 1's SIGKILL cost 1881–1884 their first attempts (`eval/results/phase2a/kill-test-1.md`).
  - Each retry read its whole file again, because a gzip stream can't seek.
- 1850 reproduces. With its candidates file moved aside, a rerun wrote all three outputs byte-identical, with the same sha256 as the committed manifest.

**26. Crops are one per box, fetched once and cached, and the display headline drops only the masthead lines that lead it.**
- There is one IIIF crop per box in `bbox_list`, in its order, which is the reading order. This replaces decision 18's single crop over every box, which takes in the columns between them on a multi-column article. In 64 of 595 multi-box 1850 articles a later box starts higher on the page, so sorting boxes by height would break the order.
- Requests to the Library of Congress:
  - They go at most one a second, with a User-Agent that names the project.
  - A busy answer is retried after 5 s, then 20 s. tile.loc.gov answered a region it hadn't made yet with a 503 after 35 s, and served the same URL a minute later in 0.2 s.
  - Crops are cached under `data/crops/`, keyed by URL, and a reply that isn't an image is never cached.
- A batch path can name a batch that LoC has since reissued. Two of the crop check's pages are recorded in `ver01` batches that tile.loc.gov no longer serves, and loc.gov lists them under `ver02`. So when a crop from a batch path is missing, loc.gov's item names the page's current service.
- The display headline:
  - Leading lines are dropped while they are the paper's title, its own place and state, an issue date, or a numbered volume or issue line. Lines of rules and stray marks are dropped anywhere.
  - A weekday or month alone isn't a date line, an issue word needs a number, and a title or place under 6 letters must stand alone as a word.
  - The stored OCR is untouched.
- Precision, judged by hand on 200 dropped lines sampled with a fixed seed from candidate headlines (`scripts/headline_drops.py`):
  - The first rule dropped such lines anywhere, and 142 of its 200 drops were correct (71.0%, 95% interval 64.4–76.8%). It took dates and words that belonged to the article, as in "Out Ghosts Next / Monday Evening".
  - The final rule's precision is 195 of 200 (97.5%, 94.3–98.9%), and 139 of the 143 lines with letters (97.2%, 93.0–98.9%).
  - The final rule drops 10,287 lines instead of 17,270. The cost is masthead blocks whose title line came out garbled, which now stay in the headline.
- The crop check (`eval/results/phase2a/crop-check.md`): 48 of 50 candidates pass (96%, 95% interval 86.5–98.9%). The two failures:
  - One page has no IIIF service: loc.gov has no item for the 1964 Arizona Tribune.
  - One article's first box, as AmericanStories gives it, is the last line of the item above.

**27. Eval A: 3.5% of candidates are ghost reports, none of 600 articles from outside them is one, and lexicon v1 stays.**
- `make eval` (`scripts/eval_a.py`) reads the counts, candidates and samples in 41 s, then writes `eval/results/eval_a.json` and eight charts to `eval/results/eval_a/`. Every sample is seeded. A rerun keeps the judgments made by hand in `composition.json`, `recall.json` and `reprint-check.json`.
- 11.2% of candidates have no state. The median candidate is 358 words long.
- OCR quality is the share of words of 3+ letters that `/usr/share/dict/words` knows, after line-break hyphens are joined and common endings come off. It is measured on 1 candidate in 20, chosen by the CRC of its id; 51,718 of those have 20 words or more. The median is 92.7%.
- Reprints:
  - Each candidate keeps a hash-chosen eighth of the 7-word runs in its first 120 words.
  - Two candidates are joined when they share a pair among their six smallest runs, so two runs in common. A pair held by more than 1,000 candidates is stock phrasing and joins nothing.
  - Linking on one shared run chained 6,720 candidates together through quoted Bible verses, and only 15 of 20 sampled pairs were the same story. With two shared runs, 20 of 20 are.
  - 80,770 clusters hold 31.4% of candidates, which leaves 801,071 distinct stories. 71,191 of the clusters span more than one paper.
- Composition: 200 candidates drawn uniformly at random and sorted by hand into seven categories.
  - **Ghost report:** a ghost, haunting, apparition or spirit manifestation, told as something that happened or was claimed to. A ghost scare that turns out to be a trapped man counts. A witch doesn't, and neither does a séance advertised for later or an essay doubting ghosts.
  - **Fiction:** stories, serials, poems, jokes and allegories.
  - **Religious:** the Holy Ghost, sermons, hymns, Sunday-school lessons and the Ghost Dance.
  - **Figurative:** a figure of speech, such as a haunt for a place someone frequents, giving up the ghost, or the spectre of war.
  - **Name or title:** a person, ship, play, lecture, book or headline, including misread names such as General Gobin read as Goblin.
  - **Social event:** Halloween parties and pranks, ghost parties and phantom drills.
  - **Other:** everything else.

  | Category | Count | Share (95% interval) | Candidates implied |
  |---|---|---|---|
  | figurative | 79 | 39.5% (33.0–46.4%) | 414,900 |
  | fiction | 47 | 23.5% (18.2–29.8%) | 246,900 |
  | name or title | 30 | 15.0% (10.7–20.6%) | 157,600 |
  | other | 23 | 11.5% (7.8–16.7%) | 120,800 |
  | religious | 10 | 5.0% (2.7–9.0%) | 52,500 |
  | ghost report | 7 | 3.5% (1.7–7.0%) | 36,800 (17,900–74,000) |
  | social event | 4 | 2.0% (0.8–5.0%) | 21,000 |
- 15 of the 200 are OCR accidents in the source text, such as "flaunting" printed as "haunting" (6) and a codling moth printed as a goblin moth. The lexicon matches what the OCR says, so only the reader, reading in context, can reject them.
- Sizes:
  - The reader's job is 1,050,459 candidates, or 801,071 if it reads one printing per cluster.
  - Atlas would hold about 22,300 ghost-report stories, counting each candidate as 1/k of a story when its cluster holds k printings. Three of the 7 reports were reprinted (7, 13 and 30 printings), so this is a rough estimate.
- Recall, from the seeded reservoirs of 2,000 articles per year, with each year weighted by its pool's size:
  - Near-miss pool: 0 ghost reports in 300, so at most 1.26% (95%), or at most 86,900 of its 6,872,539 articles. The sample's terms are spirit (210), knock (80), supernatural (4), spiritualism (4), rap (3) and seance (3).
  - All non-candidates: 0 in 300, so at most 1.26%, or at most 4.67 million of 369,263,454. This bound is loose, at 127 times the ghost reports found. Bounding the misses at the 36,800 found would take about 38,600 articles with none among them.
  - The closest calls were a séance announcement promising that spirits "will materialize" and a Kentucky girl who claims to be a witch.
- No misses means no shared vocabulary to add, so there is no lexicon v2. A re-read would take 118.6 min and 340.4 GB of downloads at four processes (decision 25).
- Both chart series colors pass the dataviz palette validator, on the light surface and on the dark one.
