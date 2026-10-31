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
  - All non-candidates: 0 in 300, so at most 1.26%, or at most 4.67 million of 369,263,454. This bound is loose, at 127 times the ghost reports found. Bounding the misses at the 36,800 found would take about 38,600 articles with none among them. Decision 30 screens that many, and finds 4.
  - The closest calls were a séance announcement promising that spirits "will materialize" and a Kentucky girl who claims to be a witch.
- No misses means no shared vocabulary to add, so there is no lexicon v2. A re-read would take 118.6 min and 340.4 GB of downloads at four processes (decision 25).
- Both chart series colors pass the dataviz palette validator, on the light surface and on the dark one.

**28. The display headline drops a date only when it is the issue's own, and a number only beside the paper's title or volume.**
- This follows the EM's review of the last five mis-drops in decision 26's sample: `IN DETROIT`, `1773.`, `April 4th.`, `NO. XXXVI.` and `4k.SATURDAY`.
- A dateline goes only when it is the issue's own, from the record's edition date:
  - Each weekday and month on the line must be the issue's.
  - The issue's weekday then settles it, because OCR misreads digits far more often than words. The Sun's `SUNDAY. DECEMBER 9.` is its masthead of the 6th.
  - Without a weekday, the day after a month and the year must be the issue's too, with OCR's I, l and O read as digits. So an advertisement's `April 4th.` in the issue of the 11th stays, as does a story's `1773.`.
- `In` followed by the paper's own place is never a masthead (`IN DETROIT` titles a column).
- A number line goes only when the leading lines hold the paper's title or its volume. This covers a bare number, and `No.`, `Number`, `Whole No.` or `Page` with a number, because `NO. XXXVI.` on its own numbers an essay.
- Rerun on the same 200 judged lines (`scripts/headline_drops.py --same`):
  - It makes none of the 5 mis-drops.
  - It keeps 37 of the 195 correct drops:
    - 22 numbers with neither the title nor the volume beside them (`NO. 40`, `NUMBER 81.`, a bare `2`)
    - 5 whole numbers
    - 3 lines of stray marks and digits
    - 4 datelines with no weekday, whose digits don't match the record's (`DELAWARE, OHIO, AUGUST 4, 1866.` in the issue of 1865)
    - 3 datelines whose weekday or month isn't the record's
  - On the 158 lines it still drops, its precision is 158 of 158 (95% interval 97.6–100%).
- Over every candidate headline, it drops 7,509 lines instead of 10,287, and nothing the old rule kept. So the judged lines it still drops remain a fair sample of its drops.
- Of the 2,778 lines it no longer drops, split as in the sample (37 correct drops to 5 mis-drops), about 2,450 are masthead lines now left in headlines (0.2% of candidates). About 330 are headline lines no longer hidden.

**29. A third of candidates have no batch path, but most of their reels do. AmericanStories' stray boxes stay.**
- 335,907 candidates (32.0%) have a scan with no batch path, so the IIIF service for their page has to come from somewhere other than `raw_data_loc`. The count for each year is in `eval_a.json` (`by_year[].no_batch_path`). By decade, the share runs from 15% in the 1820s to 37% in the 1850s. It is between 24% and 37% in every decade from the 1840s on.
- The fallback (decision 18) asks loc.gov for each page. In the crop check, it named the service for 12 of the 13 picks with no batch path. The 13th was the 1964 Arizona Tribune, which has no loc.gov item.
- loc.gov's JSON API allows 20 requests a minute and blocks an address for an hour past that ([Working Within Limits](https://www.loc.gov/apis/json-and-yaml/working-within-limits/)). Its image services allow 150 a minute.
  - A probe of 100 such pages, at one request a second, was answered 429 within its first minute, on 2026-10-30 at 04:03. Its script is deleted.
  - `crops.get` now spaces loc.gov JSON requests 3.5 s apart. At that rate, a lookup for each of the 283,546 pages would take 11.5 days.
- These candidates sit on 19,115 reels. 92.4% of them are on a reel whose batch another candidate's batch path names, and the service is built from the batch, LCCN, reel, issue and sequence. That leaves 25,595 candidates on 1,292 reels needing a lookup: about 75 minutes at one lookup per reel.
  - 220 reels hold more than one batch. For 57 of them that's a batch and its reissue (decision 26). The other 163 are split between batches, so the reel alone doesn't settle which batch a page is in.
  - A reel-to-batch map isn't built yet. It needs a crop check of its own.
- **Known limitation, not fixed:** AmericanStories can give an article a box that belongs to the item above it. In the crop check, #21's first box is the last line of the letter above, its address and signature. The crop shows that line and the OCR doesn't.

**30. A flag-word screen of 38,600 more non-candidates found 4 ghost reports, all spiritualist and all saying "spirit". Lexicon v1 finds about half the reports, and lexicon v2 is proposed but not run.**
- The draw (`make eval`, seed "eval A screen"):
  - 38,600 more articles from the random reservoirs, each year in proportion to its non-candidates. None of eval A's 300 is drawn again, so with them there are 38,900.
  - The largest year draw is 1914's: 950 of the 1,985 articles left in its reservoir. 1910 has the largest expected share, 958.
  - `draw()` now fails when a reservoir is smaller than its year's share, instead of quietly drawing fewer.
- The screen reads an article only if its headline or text holds one of eval A's flag words or a near-miss term, once line-break hyphens are joined. 1,284 do (3.3%), and 713 of those are near-miss articles. `eval/results/eval_a/screen.json` holds each one with its opening and up to six windows.
- The reading:
  - Eight reading agents judged the hits by decision 27, 160 or 161 each, split by seed. Their first reading was 1,274 no, 8 close calls and 2 reports.
  - I re-judged a seeded 10% of their negatives (127, seed "eval A screen check") from the same text, and agreed on all 127 (95% interval 97.1–100%).
  - I re-read every close call and report in full.
- The 4 reports:
  - 1856, Bordentown (the Grand River times, from the Trenton Gazette): spiritualists marry a dead man's corpse to his fiancée, on directions they say his spirit gave.
  - 1919, the New-York Tribune: Mrs. Curran says the spirit Patience speaks through her as a medium.
  - Borderline, 1898, the Abilene weekly reflector: a wife murderer's defence will be that he was under the control of spirits, with spiritualist mediums to testify. It is counted like eval A's 1904 courtroom spectre.
  - Borderline, 1918, the New-York Tribune: an Australian scout writes that he has felt a touch on the shoulder with no one there, and thinks the spirits of No Man's Land's unburied dead hover near.
  - All 4 are near-miss articles, and in each the only near-miss term is spirit. Their other words: spiritualists, spiritualistic, medium(s), disembodied, ouija board, and control of spirits.
  - Not counted:
    - living witches' shapes in testimony from 1692
    - the devil driven out of a woman
    - a psychical researcher's own spirit visiting Mars
    - the belief that a dead baby's spirit stays with its mother
    - a fictional cabman's passenger who is Aaron Burr
    - a dialect sketch
- Estimates (`eval_a.json`, `recall.screen`; `recall.svg` now shows them):
  - **Non-candidates:** 4 in 38,900, so 0.010% (0.0040–0.026%), or about 38,000 (14,800–97,600) of 369,263,454 articles.
  - **Near-miss pool:** 4 in 1,013 (the 713 drawn and eval A's 300), so 0.39% (0.15–1.0%), or about 27,100 (10,600–69,500) of 6,872,539.
  - **Recall:**
    - The candidates hold about 36,800 reports (decision 27), so lexicon v1 finds about 49% of them.
    - With the most reports the interval allows outside the candidates, it finds at least 27%.
    - Across the candidates' own interval (17,900–74,000), the floor runs from 16% to 43%.
  - Counting only the 2 clear reports gives about 19,000 missed (5,200–69,200), so recall would be about 66%, and at least 35%.
- **Caveat:** the screen sees only the reports that hold a flag word or a near-miss term.
  - With their lexicon terms masked, 5 of eval A's 7 reports still hold one (71%, 36–92%).
  - The two that don't are the 1904 courtroom spectre and the 1916 Peking legation, which calls its ghost a "shade".
  - So the screen may miss about 3 in 10 of the reports outside the candidates (2 in 7). If it does, the true number is about 1.4 times these estimates.
- **Lexicon v2, proposed to the EM and not run.** Each candidate term was measured on the 38,900 judged articles:

  | Term | Articles in 38,900 | Candidates added | Reports caught |
  |---|---|---|---|
  | spiritualism, spiritualist(s), spiritualistic | 8 | ~76,000 | 2 |
  | spirit(s) and medium(s) in one article | 8 | ~76,000 | 2 |
  | spirit world, land, control, message, manifestation, circle or photograph; control of or by spirits; disembodied; spirits of the dead or departed | 5 | ~47,000 | 2 |
  | ouija, planchette | 1 | ~9,500 | 1 |
  | séance, moved from the near-miss lexicon | 0 | 0 | 0 |

  - Together they match 17 articles: about 161,000 more candidates (+15%), and they catch 3 of the 4 reports. About 18% of what they add are reports (6–41%), against 3.5% for v1.
  - Left out: materialize, which matched 7 articles and no report. No term catches the 1918 scout's "spirits".
  - Cost: a full re-read takes 118.6 min and 340.4 GB of downloads (decision 25). The reader's job would grow to about 1.21 million candidates.
  - The EM accepted it as step 2A.8. Decision 31 has the re-read and what it measured.
- `eval_a.json` now records `/usr/share/dict/words`'s sha256 (`be41ad97963bf8da…`) and its 235,976 words, so the OCR-quality figure can be checked on another machine.

**31. Lexicon v2 is run. Its spiritualist rules add 185,663 candidates (+17.7%), and 7.0% of them are ghost reports. Its recall is about 84%, but that figure is in-sample.**
- The rules (`lexicon.py`, version v2), each recorded by name in a candidate's `terms`, so any one of them can be dropped by filtering, without a re-read:
  - `spiritualism`: spiritualism, spiritualist(s), spiritualistic
  - `seance`: séance(s)
  - `spirit_phrase`: spirit world, land, control, communication, manifestation, message, photograph, circle or medium; control of or by spirits; disembodied; spirits of the dead or departed
  - `ouija`: ouija, planchette
  - `spirit+medium`: spirit(s) and medium(s) anywhere in one article
- v1's terms come first in the pattern, so where a v1 term and a new one match at the same place, v1's term is the one recorded.
- v1 is kept. Its candidates and samples were moved, not deleted, to `data/archive/lexicon-v1/`, with copies of its counts and manifests.
  - `make eval-v1` runs eval A on that archive and reproduces `eval_a.json` and its charts byte for byte, apart from `generated_at`. So eval A's composition, recall and screen stay the record of v1, and no hand judgment was redone.
  - `make eval` now writes v2's EDA to `eval_a_v2.json` and six charts in `eval_a_v2/`. It then writes the comparison with v1 to `eval_a_v2/lexicon_v2.json`, and the judged sample to `added.json` (`scripts/lexicon_v2.py`).
- The re-read covered all 180 years at four processes, 14:49–16:50Z (120.6 min) for 340.4 GB:
  - every year finished at the first attempt
  - peak memory was 551 MB (1919)
- Checks:
  - All 180 manifests share one code version, `2d6ff0faaf81`, and lexicon v2.
  - v1 ⊆ v2: all 1,050,459 v1 candidates are still candidates, and none of the 185,663 added holds a v1 term.
  - 1850 reproduces. With its candidates file moved aside, a rerun wrote all three outputs byte-identical, with the sha256 its manifest records.
  - Disk: the v1 archive and the v2 outputs take 4.1 GB, within the 10 GB budget, and 36 GiB are free.
- v2's EDA:
  - 1,236,122 candidates (3,338 per million, against v1's 2,837) and 6,695,792 near-miss articles.
  - 91,301 reprint clusters hold 30.3% of candidates, which leaves 952,591 distinct stories.
  - 32.0% of candidates have no batch path, and 93.0% of those are on reels whose batch is known. That leaves 27,817 candidates on 1,258 reels for loc.gov, against v1's 25,595 (decision 29, scratch `reels.py`).
- The 200: 200 added candidates drawn at random (seed "eval A v2 added"), judged with decision 30's protocol:
  - **Reading:** four reading agents read 50 each, split by seed. Their first reading was 169 no, 21 close calls and 10 reports.
  - **Blind check:** I re-judged a seeded 10% of their negatives (17, seed "eval A v2 added check") from the same text, without their notes, and agreed on all 17 (81.6–100%).
  - **Full reading:** I read every close call and report in full.
  - **Beyond decision 30's protocol:** I also read in full the 8 negatives outside the blind check that the agents' notes called near. The ninth was in the blind check.
  - **Outcome:** all 10 of the agents' reports stand. 3 of the close calls are reports and 18 are not, and 1 of the near negatives is a report. In `added.json`, `rejudged` is "sample" for the blind check and "full" for an article I read in full.
- **14 of the 200 are reports: 7.0% (4.2–11.4%), so v2 gains about 13,000 (7,830–21,200).**
  - That is twice v1's 3.5% (decision 27).
  - 2 of the 14 are borderline. Without them, 12 (6.0%, 3.5–10.2%) give about 11,100 (6,430–18,900).

  | Rule | Candidates | Added | Added holding only it | In the 200 | Reports | Rate (95%) | Reports among the added |
  |---|---|---|---|---|---|---|---|
  | spiritualism | 74,516 | 68,183 | 54,411 | 82 | 8 | 9.8% (5.0–18.1%) | ~6,650 (3,430–12,330) |
  | seance | 34,206 | 30,466 | 21,656 | 38 | 4 | 10.5% (4.2–24.1%) | ~3,210 (1,270–7,350) |
  | spirit_phrase | 42,186 | 35,695 | 24,537 | 37 | 4 | 10.8% (4.3–24.7%) | ~3,860 (1,530–8,820) |
  | spirit+medium | 79,374 | 72,856 | 57,676 | 67 | 3 | 4.5% (1.5–12.4%) | ~3,260 (1,120–9,000) |
  | ouija | 6,389 | 5,855 | 5,124 | 6 | 0 | 0% (0–39.0%) | at most 2,290 |

  - A candidate can hold several rules, so the rows overlap. "Added holding only it" is what dropping that rule alone takes away.
  - **ouija is flagged:** no report in its 6. Dropping it is the EM's call. It would take 5,124 candidates away by filtering.
- **Marginal yield**, which the EM asked for to decide which rules to keep. It counts the reports in the 200 that one rule catches and no other term catches, so it is what dropping that rule alone would lose. No rule was tuned or narrowed on the 200.

  | Rule | Reports only it catches, of the 200 | Reports among the added that only it catches | Sampled articles holding only it | Their rate (95%), of the added holding only it |
  |---|---|---|---|---|
  | spiritualism | 4: 2.0% (0.78–5.0%) | ~3,710 (1,450–9,340) | 64 | 6.3% (2.5–15.0%) of 54,411 |
  | seance | 2: 1.0% (0.27–3.6%) | ~1,860 (510–6,630) | 28 | 7.1% (2.0–22.6%) of 21,656 |
  | spirit_phrase | 2: 1.0% (0.27–3.6%) | ~1,860 (510–6,630) | 24 | 8.3% (2.3–25.9%) of 24,537 |
  | spirit+medium | 2: 1.0% (0.27–3.6%) | ~1,860 (510–6,630) | 57 | 3.5% (0.97–11.9%) of 57,676 |
  | ouija | 0: 0% (0–1.9%) | at most 3,500 | 3 | 0% (0–56.2%) of 5,124 |

  - 10 of the 14 reports hold a single rule. Each of the other 4 holds two or more: 1875's Eddys, 1922's Conan Doyle, 1923's Vale Owen and 1924's Chicago meeting.
  - Two of the single-rule reports are the borderline ones: Allut (spirit_phrase) and Hodgson (spiritualism). Without them, spirit_phrase alone catches 1 and spiritualism alone catches 3.
  - In 2A.7's screen, spirit+medium caught no report that another rule missed. Here it alone catches two: 1857's Middlebury trance medium and 1859's Plymouth convention.
  - spirit+medium is also the largest rule, with the lowest precision. Its candidates holding no other rule are reports at 3.5%, the same rate as v1's candidates.
  - `lexicon_v2.json` gives each rule's `marginal` (over the 200) and `only` (over its sampled articles holding only it).
- **The EM's call (2026-10-30): keep all five rules.**
  - Each of spiritualism, seance, spirit_phrase and spirit+medium catches reports that no other rule does.
  - ouija's 0 of 6 rules nothing out (0–39%), and it costs only 5,124 candidates, 0.4% of the reader's job. 2C's term strata measure it.
- The 14 reports:
  - 1857, Middlebury: a spirit called Judd speaks through a trance medium at Union Hall.
  - Borderline, 1857: in the Picaud ("real Monte Cristo") narrative, printed as true, the dying Allut says he has seen and spoken with a soul separated from its body.
  - 1859, Plymouth: a spiritualist convention's president says the spirits of Washington and Lafayette held a Masonic rehearsal in his presence.
  - 1869, Muskingum County: a family say the spirit world told them they will inherit $50,000 each.
  - 1873, Wilmington: a spiritualists' excursion whose circle materialized the dead.
  - 1875, Rutland: fourteen spirits materialize at the Eddys'.
  - 1895, Waterloo, Oregon: a speaker at a meeting is controlled by Sitting Bull's spirit.
  - 1898, Sacramento: John Slater's test séance.
  - Borderline, 1907: an editorial reports the claim that the dead Professor Hodgson has communicated, as he promised.
  - 1920, Trenton: Lincoln's spirit predicts that Cox will be elected.
  - 1922: Conan Doyle has spoken with his dead son at séances.
  - 1923: a review of the records of Victor Hugo's table-turning séances.
  - 1923, Washington: Rev. G. Vale Owen lectures on his messages from his dead parents and daughter.
  - 1924, Chicago: a voice in a darkened spiritualist meeting.
- Interpretation calls, for the EM to overrule:
  - A first-person claim of communication with a named dead person counts, in a lecture or an interview too, like decision 30's 1919 Curran report. This covers Vale Owen and Conan Doyle.
  - Jokes told as news don't count: a "shade" questioned about a lawsuit, automatic writing that names the Devil. Neither do hypnotic clairvoyance or a trance prophecy with no spirit.
  - The two borderline kinds go to `POLICY.md`: a claim inside a narrative whose truth is doubtful, and a particular claim told inside a general essay.
- Recall, in-sample. v1's screen (decision 30) was read again with v2:
  - v2 makes 17 of its 38,900 articles candidates. They include 3 of its 4 reports, from 1856, 1898 and 1919. The 1918 scout's "spirits" is still missed.
  - **Missed:** 1 in 38,883, so 0.0026% (0.00045–0.015%), or about 9,500 (1,680–53,800) of 369,077,791 non-candidates.
  - **Recall:** the reports in v1's candidates (about 36,800) and those v2 adds (about 13,000), over those plus the missed, give **84%**. With the most misses the interval allows, it is at least 48%, and across the found reports' interval that floor runs from 32% to 64%.
  - Without the 2 borderline reports among the 200, recall is 83%, and at least 47%.
  - **Caveat:** v2's rules were chosen from this screen's misses, so it catches them by construction, and the 84% is optimistic. 2C's eval B gives the independent figure with the reader's screen of the random reservoirs. Decision 30's caveat also stands: the screen sees only reports that hold a flag word or a near-miss term.
- Cost: no money, only machine time and 340.4 GB of downloads. The reader's job grows from 1,050,459 candidates to 1,236,122 (+17.7%). The Tinker credit check weighs that before the full pass.

## Phase 2B (2026-10-30)

**32. Atlas is the serving index, not the archive. It is built to M0's limits and to nine rules.**
- **M0's limits**, from the MongoDB docs as the EM checked them on 2026-10-30, in the EM's Atlas notes (`ATLAS-PLAN.md`):
  - **Storage:** 0.5 GB, a hard limit. It counts uncompressed BSON plus indexes. `sample_mflix` already uses about 239 MB: Phase 1 measured 239,185,920 bytes.
  - **Search indexes:** 3 in all, Search and Vector Search together. The plan uses exactly three: Search and Vector Search on `reports`, and autocomplete on `places`.
  - **Throughput:** 100 operations a second, throttled above that.
  - **Network:** 10 GB in and 10 GB out per rolling 7 days.
  - **Other:** 500 collections, and 32 MB for a sort in memory.
- **The rules:**
  1. Atlas holds stories, places, cases and stats only. The 340 GB is streamed and never stored, and candidates, samples and reader labels stay in local files, one per year.
  2. The pipeline is partitioned by year. The year is the Temporal activity, the unit of retry and the cache key. The static export is partitioned by state and then town, with one more file per calendar day for "Printed on this night".
  3. One collection per entity, never one per year. Collections per year would multiply the indexes and split the town drawer's queries across years. Nor could each have a Search index under the cap of 3.
  4. Category fields get no index of their own: outcome, kind, place type, precision, decade and state.
     - They are token fields in the Search index and filter fields in the vector index.
     - The reel's counts are precomputed into `stats`.
     - A partial index on `case_id` covers only the 30–60 investigated stories.
  5. Atlas Search mappings are static, not dynamic. They map the fields that are searched or filtered, and nothing else: no printings and no quotes.
  6. Heavy fields stay small:
     - **Embeddings** are BinData vectors (float32 or int8), never arrays of doubles. A 384-dimension embedding takes about 4.8 KB as an array, 1.5 KB as float32 and 0.4 KB as int8. Decision 33 checks that BinData vectors work on M0.
     - **Crop URLs** are derived from the scan location and the boxes when they are read, not stored.
     - **Printings** are compact references embedded in their story.
  7. Loading:
     - one activity per year
     - `bulk_write` of `ReplaceOne(upsert=True)` on stable `_id`s, with `ordered=False`, about 1,000 documents a batch, and a retry when throttled
     - indexes built after the load
     - `db-verify` run only once the Search and Vector indexes can be queried
  8. The budget comes from measurement. 2B measures the real bytes per story, and the free space divided by that says how many stories fit with full text (`BUDGET.md`).
     - The free levers in rule 6 come first. Dropping `sample_mflix` is the owner's call.
     - Quality is never cut to fit. If full-text fuzzy search over every story won't fit, the options go to the owner rather than search shrinking to excerpts. One such option is the Flex tier, which costs money and needs the owner's yes.
  9. To weigh in 2B and 2C: cluster reprints before the reader, read one printing per cluster, and split gold, dev and train by cluster. That means less work for the reader and no leakage.

**33. The data layer is built: models, validators generated from them, BinData embeddings and `make db-init`. M0's third Search index waits on the owner.**
- **Models** (`paperghosts/schemas`): `Report`, `Place`, `Case` and `Stat`, as ARCHITECTURE section 4 now gives them.
  - **No nulls:** a document is stored without its empty fields.
  - **IDs:** the model checks SRS section 5's, which a validator can't: a report is `r_` plus its primary article, and a case is `c_` plus its report.
  - **`versions`:** every record carries the code's SHA and whichever lexicon, model, adapter and prompt made it. It replaces section 4's `reader`.
  - **Embeddings:** an embedding must be a float32 or int8 BinData vector of 384 dimensions.
  - **Cross-field rules:** the model also checks three more.
    - A stated value needs a quote that verified. Atlas's validator enforces this one too.
    - A report's year, month_day and decade must be its date's.
    - A printing's issue must be its date and its edition.
- **Printings** (`paperghosts/store/printings.py`), checked over all 1,236,122 v2 candidates (the EM's review):
  - **Location:** a printing is located by its member name, as `1910-04-12_p8_sn84022472_0029586686A_1910041201_0396.json` shows. That gives the date, a page token, the LCCN, the reel, the issue (the date and a two-digit edition) and the frame.
    - Every member name parses, and every issue is its date and two digits.
    - So edition, reel, issue and frame are required.
  - **LCCN:** 10,871 records (0.88%) have none, and those take the member's. Every record that has one agrees with its member name.
  - **Page:** the page comes from the scan record only, where it is a number for 19.9% of candidates. It is never taken from the member name's page token.
    - In 1910, the article ID and the member name differ only in that token, for 18,082 of 25,346 candidates (71.3%). Their date, LCCN, reel, issue and frame always agree.
    - In those candidates the member gives a page number that the scan record doesn't confirm: the scan says "na" or nothing.
    - Where the scan's page is a number, the two always agree.
  - **Service:** the IIIF service comes only from the scan's batch path, which 68.0% of candidates have. Where a candidate has both, the batch path's frame differs from its member's in 20,643 (2.5%), and the reel in 396. For the frame, decision 35 supersedes this.
    - Example: the member `…_1910021001_0164` and the jp2 `sn82016187/100493962/1910021001/0163.jp2`.
    - So a page located without a batch path can be the wrong one. Its crop waits for a check, whose error 2B's reel-map validation measures (`BUILD-PLAN.md`).
- **Validators** (`paperghosts/store/validators.py`): generated from the models.
  - Atlas reads draft 4 with `bsonType`, so references are inlined, `const` becomes `enum`, integers become int or long, and a tuple becomes `items` with `additionalItems: false`.
  - A keyword Atlas lacks raises an error.
  - The collections validate strictly, with errors.
  - **Tests:** 27 invalid documents cover required fields, enums, GeoJSON, a printing with no frame, a stated value with no verified quote, an embedding stored as an array, and stored crop URLs. The model, an offline checker in the tests and Atlas itself each reject every one, Atlas with error 121 (the test marked `atlas`). The valid documents pass all three.
- **BinData vectors work on M0** (`scripts/bindata_check.py`, `eval/results/phase2b/bindata_check.json`):
  - The test set: 2,000 vectors of 384 dimensions, in 40 clusters, each stored as float32 and as int8, under one Vector Search index.
  - **Exact search:** for both types, Atlas returns numpy's 10 nearest neighbours in the same order for all 20 queries. Its scores are within 1e-7 of (1 + cos)/2.
  - **Approximate search:** recall is 1.0 at 200 candidates.
  - **Sizes:** an embedding takes 4,898 BSON bytes as an array of doubles, 1,554 as float32 and 402 as int8.
  - **Cleanup:** the index was queryable in 28 s. The scratch collection and its index were then removed.
- **`make db-init`** (`paperghosts/store/db_init.py`):
  - It builds the four collections, their validators, section 4's indexes and the three Search indexes, as static mappings in code.
  - It touches only database `paperghosts`, and in it only the collections in the plan. Phase 1's `skeleton` is left as it is.
  - Each change to the models made one run update the validators it changed. The run after printed "nothing to change", which was true of the final model too.
- **The third Search index can't be created yet.**
  - M0's cap of three counts every database in the cluster, and `sample_mflix.movies` holds a Search index named `default`. So `places_search` isn't created.
  - `make db-init` names the index it couldn't create, and exits 1 instead of stopping halfway.
  - Freeing the slot is the owner's call, as dropping `sample_mflix` is (decision 32, rule 8). The EM is taking it to the owner with the budget.
  - `places_search` stays in the code, so db-init creates it once there's a slot. Until then, it's pending.
  - The cluster also holds a database `cubby`, with one collection, which isn't this project's. Nothing here touches it.
- **The budget** (`BUDGET.md`, `eval/results/phase2b/budget.json`, `scripts/budget_probe.py`):
  - **What counts:** Atlas counts data size plus B-tree index size, from `dbStats`, against the cap. Search indexes aren't in `dbStats`, and Free clusters have no Search size metrics, so by the docs they don't count. No page says so outright.
  - **Free space:** of the 500,000,000 bytes planned for, 350.5 MB is free with `sample_mflix` and 499.4 MB without it.
  - **A story's size:** 6,199 bytes before its printings, 454 per printing and 508 of indexes. Each figure is the larger of the 1,000 sampled candidates' and the 24 judged reports'.
  - **Index sizes:** these come from a fresh scratch collection that was dropped afterwards. `reports` kept its index pages after an earlier probe run, which made its own sizes useless.
  - **The top of the range** is 95,203 printings:
    - At v1's ratio of 57,744 stories, it needs 430.5 MB as stored. That fits only without `sample_mflix`, or with every lever including int8 (346.9 MB).
    - At one story per printing, it needs 681.8 MB, which M0 can't hold in any form. The smallest form is 552.9 MB.
  - **The point estimates** of 30,183 stories need 225 MB, which fits either way.
  - **The levers:**
    - int16 boxes, the title lookup and the derived headline save 17 MB at the top of the range, all without loss.
    - int8 saves 66.5 MB more, but only after 2D checks it on real embeddings.
    - Turning rule 6's levers off would cost up to 206 MB.
  - **Next:** the owner's options are listed in `BUDGET.md`, and the EM takes them to the owner with the Search slot.

**34. Every paper's title, place and state as printed, with its state today; and a GeoNames geocoder, checked against each paper's loc.gov title record, which puts 98.0% of papers' places right.**
- **BUDGET.md's third scenario** (`scripts/budget_stories.py`):
  - Each judged report counts as 1/k of a story when its v2 cluster holds k printings.
  - In v1's candidates, eval A's 7 give 0.608 stories per printing, decision 27's ratio again.
  - In the candidates v2 added, 17 reports give 0.802.
  - So the top of the range is 61,960 stories, not 57,744. It needs 458.8 MB as stored, and 370.1 MB with every lever. Nothing fits beside `sample_mflix` any more, and everything still fits without it.
- **The title parser** (`paperghosts/geo/titles.py`) gives each title string's title, and its place, county and state as printed. It also gives the place and state the cataloguer supplied in brackets, and the years.
  - A bracket after the place adds to it.
  - A bracket after the state, or one marked `i.e.`, supplies a place. A bracket after the state that starts with a state supplies only a state.
  - A bracket standing alone supplies the whole place, and `[sic]` affirms what's printed.
  - A single part is the place, unless it's an abbreviated state, so Washington and New York stay cities.
  - It also handles `[volume]`, `[microfilm reel]`, HTML entities, and UTF-8 that was read as Windows-1252.
- **The parser's test** (`tests/fixtures/titles.json`):
  - The draw: 200 LCCNs at random from the candidates' 3,336 (seed "2B title parser"), each by its longest title string.
  - Five LCCNs in that draw have no title string at all. A second seeded draw replaced them.
  - I checked all 200 outputs by hand. 199 were right first time, and #6's `H.T.`, Hawaii Territory, was the one fault.
  - The geocoder's draw found one more fault, in `Dakota [Dakota Territory, i.e. S.D.]`. It is fixed, and of the 4,531 title strings among the candidates, it's the only one that changed.
  - `state_name` maps a printed state to its modern one. The exception is the territory initials that stood for two states (W.T., N.T., I.T., D.T. and Dakota), which a bracket or the record settles.
- **Then and now:** `then_and_now` shows a state that has changed.
  - 1835's Virginia free press is printed in "Charlestown, Va. (now W.Va.)" (sn84026784).
  - 1834's Alexandria gazette is printed in "Alexandria, D.C. (now Va.)", because Alexandria returned to Virginia in 1846.
  - Where the record check puts a paper's point at its record's place, the display names the record's town too: "East Saginaw, Mich. (now Saginaw)". Two spellings of one town, such as Charlestown and Charles Town, aren't a new name.
  - A paper that moved keeps its printed town: Zajedničar stays "Allegheny, Pa.", not "now Youngstown". A first build compared the names alone, and 8 of the 14 towns it showed as "now" were moves.
- **Title records:** 424 LCCNs give no place or state in any title string, 45 of them having no title at all. They hold 22,313 candidates.
  - Each is asked for once from loc.gov's item JSON, at least 3.5 s apart, and cached with its URL, retrieval date and status.
  - A 404 is cached. A server error that outlasts the retries is counted and not cached, so the next run asks again.
  - Cloudflare's 520–524 now count as busy, and `crops.get` retries them.
  - All 424 records are cached. 423 were found, and 1 wasn't: sn88084224, The Western star (Texas), a 404. None failed.
  - The final build made 327 requests in 39 minutes, 7.2 s each on average. It found the other 97 already cached: the draw's papers, fetched first, and those from a first build that a 520 stopped.
  - The records of the accuracy draw's 200 papers came next, queued after that fetch and never beside it. 23 were cached already, and 177 requests took 20 minutes. One got a 503 that outlasted the retries, so it wasn't cached, and the next run fetched it. All 200 have a record.
  - The other LCCNs' records come in 2D, and only for the papers among stored printings, as decision 29 does for pages (`BUILD-PLAN.md`).
- **The title lookup** (`scripts/titles.py`, `data/titles/titles.json`, the `Title` model) has one entry per LCCN: the title, the place and state as printed, what was supplied, the state today, and the two together. It also keeps the place, county and state that a fetched record catalogues today (`catalogued_place`, `catalogued_county` and `catalogued_state`).
  - Of the 3,336 LCCNs, 2,912 take their place from a title string and 423 from a title record. One has neither: The Western star.
  - 115 show a state that has changed.
  - 599 have a record. 15 of those records name a town other than the printed one, because the town was renamed or merged, or the paper moved. Only East Saginaw, whose point the check takes from its record, is shown with the record's town.
- **GeoNames** (`paperghosts/geo/geonames.py`):
  - The data: GeoNames' US, Puerto Rico and Virgin Islands dumps of 2026-10-30, with their state and county codes.
    - `US.zip`: 71.1 MB, 2,241,410 rows
    - `PR.zip`: 0.3 MB, 8,277 rows
    - `VI.zip`: 0.1 MB, 1,872 rows
  - A territory's municipios or islands serve as its counties. No title names any other territory.
  - `data/geonames/manifest.json` records each file's URL, retrieval date, size and sha256, and the CC BY 4.0 licence.
  - Only populated places count. GeoNames' 107,543 "(historical)" places in class S are kept apart as ghost towns, and only a title record's county can accept one.
  - Names compare without accents, case, punctuation or spaces, so "Charlestown" is "Charles Town", and "St." reads as Saint.
  - Ties break in this order:
    1. the printed county
    2. a living place before a section, and before a historical, abandoned or destroyed one
    3. a match by name before one by alternate name
    4. a capital or county seat
    5. the larger population
    6. the lower ID
  - The space-free names came from this check's first look at Charlestown. GeoNames lists Charlestown among the capital Charleston's alternate names, and Charleston's population won.
- **The record check** (`paperghosts/geo/papers.py`, from the EM's review). loc.gov's title record gives each paper's city, county and state as catalogued today.
  1. The printed place is geocoded in its modern state, the cataloguer's bracketed place first.
  2. It is checked against the record's county: GeoNames' county (admin2) has to be one the record names, in one of the record's states. A paper that moved has all its counties and states.
  3. A place outside the record's county, or no place at all, gives way to the record's place, geocoded in its county. The printed place stays for display, with the record's town: "East Saginaw, Mich. (now Saginaw)".
  4. Failing that, a ghost town of the record's name in the record's county counts, flagged historical. Clifton, S.D. is the case.
  5. Failing that, there is no point. A pin that disagrees with the record is the dangerous kind of answer.
  - A record that names no county GeoNames has in its state can't check a place. The printed place stands, or, where that resolves to nothing, the record's place, unchecked.
    - Alaska is one such case: loc.gov files Seward under "Seward", and GeoNames files it under the Kenai Peninsula Borough.
    - Connecticut is another: GeoNames files its places under planning regions now.
  - **I made two of the check's rules on these 200:**
    - Alaska's rule. The first run, with 23 records cached, turned Seward from a right answer into no point.
    - Reading the record's `location_state` list, as your review said, instead of the one state in its `location_str`. Zajedničar (Allegheny, Pa.) moved to Youngstown, Ohio, and with Ohio alone, the check replaced a right answer with Youngstown.
- **Accuracy on the papers** (`scripts/geocode_check.py`, `eval/results/phase2b/geocoder.json`, answers in `geocoder_expected.json`):
  - The draw: 200 distinct (place, state) pairs, by walking the papers in seeded order (seed "2B geocoder"). I checked each by hand.
  - Each pair is geocoded twice: by its printed place alone, and with the record check against its paper's record.
  - **Without the record check, 194 are right: 97.0% (93.6–98.6%).** 195 resolve, and 194 of those are right: 99.5% (97.2–99.9%). The one wrong pin is Bloomington.
    - Ponce, P.R. is right now, because the Puerto Rico dump is an input.
    - Before the dump, 193 were right (96.5%). Before the parser fix the draw prompted, 192 were (96.0%).
  - **With the record check, 196 are right: 98.0% (95.0–99.2%).** 198 resolve, and 196 of those are right: 99.0% (96.4–99.7%).
    - The check settles East Saginaw, under Saginaw, and Clifton, as a ghost town.
    - **It leaves 2 wrong pins, one more than without it:**
      - Bloomington still. loc.gov's own record puts Bloomington in Story County: it names Story and Muscatine, so the check agrees with the wrong Bloomington. Its record can't catch it.
      - Norfolk and Portsmouth, which the check adds. The record names no county and gives Portsmouth as its place, so the unchecked rule pins Portsmouth, about 2 km from Norfolk. Its notes say the paper was published in both. I kept my expected answer, Norfolk, from the title.
    - No printed place that resolved was replaced.
  - What the records made of the 200:

    | Outcome | Papers |
    |---|---|
    | agrees | 177 |
    | has no county to check: independent cities, D.C., Alaska and Ponce | 14 |
    | can't be checked: Connecticut's planning regions, and Seward | 4 |
    | found what the printed place didn't: East Saginaw | 1 |
    | a ghost town in the record's county: Clifton | 1 |
    | found what the printed place didn't, unchecked: Norfolk and Portsmouth | 1 |
    | disagrees, and its own place isn't in GeoNames: Lardo and New Oregon | 2 |

  - Only one of the three merged towns is catalogued under its successor: East Saginaw, under Saginaw.
    - The Long Valley advocate's record names Lardo and Roseberry, in Idaho County, its county then. GeoNames has Roseberry and McCall in Valley County.
    - New Oregon's record names New Oregon itself, which GeoNames doesn't have.
    - Both stay as no point, which is the safe failure.
  - Some are right under an old name or a merger: Allegheny is Pittsburgh, and Daytona is Daytona Beach. Fort Wrangel, Sumterville, North Yakima and Langston City are old names their towns list.
  - **The failures, by kind:**

    | Kind | Without the check | With it | Cases |
    |---|---|---|---|
    | merged into a town that doesn't list its name | 3 | 2 | East Saginaw into Saginaw, which the check settles; Lardo into McCall; New Oregon into Cresco |
    | renamed, with its old name now another town's | 1 | 1 | Bloomington, Iowa, Muscatine's name until 1849: a wrong pin either way, on a living Bloomington in Story County |
    | two towns named as one place | 1 | 1 | "Norfolk and Portsmouth, Va.": no point without the check, and a pin on Portsmouth with it |
    | a ghost town filed outside populated places | 1 | 0 | Clifton, S.D., which GeoNames has as "Clifton (historical)" in class S |
    | outside GeoNames' US dump | 0 | 0 | Ponce, P.R., right since the Puerto Rico dump became an input |

  - **These 200 are in-sample for the check.** Its fixes come from their failures, through the EM's review, and so do two of its rules. 2D measures it, and any further fix, on a fresh draw (`BUILD-PLAN.md`).
- **The 24 judged reports' story places,** as their text gives them: an early look at what the reader will extract.
  - The text gives a town and a state for only 3. The geocoder puts all 3 right (43.8–100%).
  - 9 name a town but no state. Datelines like "CHICAGO, Jan. 1" are the usual case.
  - 8 name no town at all, or only a venue such as "the National Theater".
  - 4 are abroad: Jersey, Peking, Blickling and France.
  - **For the 9 with a town only, the paper's own state is a poor guess:**
    - right for 3, the local stories at Middlebury, Waterloo and Chittenden
    - a wrong place for 2: Adamsville lands in Pennsylvania, and Easton in Indiana matches West Newton, which lists Easton as an alternate name
    - nothing for 4: Chicago in Connecticut, Kansas and Utah papers, and Bordentown in a Michigan one
  - **So a story place that is only a town resolves from a county or state the text gives, or from its dateline. Otherwise it stays unresolved, and it never falls back on the paper's state** (the EM's review). 2C measures the rule on its gold set, and 2D applies it (`BUILD-PLAN.md`).

**35. The reel-to-batch map gives 93.9% of the candidates with no batch path a batch from local data, and it's right for 99.8% of hidden issues. A page it locates is checked by its size and its OCR before its crop is shown, and the check rejected all 90 wrong frames tried. Where a member and its batch path name different frames, the member's was the page, and the stored service now takes it.**
- **The map** (`paperghosts/ingest/reels.py`, built by `scripts/reel_map.py` into `data/reels/map.json`, 10.6 MB): for each LCCN and reel, the batches its pages' batch paths name, and the issues each batch holds there.
  - Its source is the 1,101,110 pages with a batch path, of the 1,586,714 distinct pages among the candidates and samples. They cover 24,620 reels and 742,015 issues.
  - A reel is keyed by its LCCN and reel number, as decision 29 counted. A page is filed under its batch path's reel and issue, never its member's.
  - Building it asks loc.gov nothing, and takes 26 s.
- **Coverage, reconciled with decision 31** (`eval/results/phase2b/reels.json`):
  - From the candidates' batch paths alone, the map reproduces decision 31 exactly. 367,251 of the 395,068 candidates with no batch path (93.0%) sit on a reel it holds, and 27,817 on 1,258 reels don't.
  - The samples' batch paths add 589 reels. With them, 370,949 are covered (93.9%), and 24,119 on 1,000 reels aren't.
  - 6,530 of those 24,119 have no reel in their member name ("no_reel"), so no reel map can place them.
  - No loc.gov lookup ran for the 24,119.
- **The rule** (`reels.ranked`, whose first batch is `reels.pick`), for a page with no batch path:
  1. A reel with one batch gives it.
  2. On a reel with several, batch names are tried by how near their nearest issue is to the page's in date. A tie goes to the name with more of the reel's issues.
  3. Within a name, its latest version comes first: ver02 before ver01. A version can come without an underscore, as in `ncu_frankenver01`.
  4. `info.json` decides. A batch that doesn't hold the page answers 404, and the next batch is tried. Where none holds it, loc.gov's item for the issue names it.
  - The batch path wins wherever it exists, so the map is only for pages with none.
- **The hidden-issue check:** every issue on every reel was hidden in turn, all its pages at once, and its batch picked from the rest of its reel.
  - 740,969 issues could be tested. The 1,046 reels that hold a single issue can't be.
  - **Overall, 739,317 are right: 99.78% (99.77–99.79%).** Every page on a reel with one batch is right.
  - **On the 257 flagged reels, 9,616 of 11,268 are right: 85.3% (84.7–86.0%).** By batch name, with a reissue's versions taken as one, 10,594 are: 94.0% (93.6–94.4%).
  - All 1,652 misses are on flagged reels. 978 name a reissue's other version, and 674 another batch.
  - By page, the flagged reels' pages are right for 13,439 of 16,324 (82.3%), and their candidates for 11,102 of 13,677 (81.2%).
  - 173 issues lie in two batches.
- **Flagged reels: 257,** each listed in `reels.json` with its batches' date ranges and its candidates with no batch path. 5,232 such candidates sit on them.
  - 62 are reissues: one batch name in two or more versions. Their versions alternate along the reel, and half their issues (978 of 1,958) have the older version's batch path.
  - 195 are split between batch names:
    - 127 interleave over the same years
    - 53 follow one another
    - 15 are one batch under two awardee codes, such as `cohi_dearfield` and `ohi_dearfield`
- **Which batch serves** (`scripts/page_check.py reels`): 25 split and 25 reissued reels were drawn (seed "2B.3 reels"), each with one candidate page that has no batch path. `info.json` was asked of every batch each reel holds.
  - **The rule's first batch serves 42 of the 50: 84.0% (71.5–91.7%).** Trying the reel's batches in turn finds a batch for 46: 92.0% (81.2–96.8%).
    - On split reels, the first batch serves 23 of 25. The other two are served by the reel's other batch: `vi_balikun`, and `cohi_dearfield` where the rule picked `ohi_dearfield`.
    - On reissued reels, the first batch serves 19 of 25:
      - 2 are served only by the older version: `dlc_thompson`'s ver02 lacks some of ver01's issues.
      - 4 are served by no version the map knows (`az_campfiregoneout`, `dlc_davis` and `vi_ironmaiden` twice), so they need loc.gov.
  - 11 pages are served by two batches. Where the recorded size is exact, both have it.
    - `vi_kernals`' two versions differ by about 10 pixels, on pages of approximate size, so which one AmericanStories read can't be told.
  - Where one batch serves a page of exact size, that batch has the recorded size: 23 of 23.
- **Where a page's member and its batch path name different frames, the member's frame was the page: 18 of 18 (82.4–100%).** So the EM changed decision 33's rule for the frame.
  - Calibration drew 20 candidate pages whose member names another frame or reel than their batch path does (seed "2B.3 calibrate"). 18 differ only in the frame, and 2 in the reel. Each was checked on the page its member names, in its batch path's batch.
  - All 18 member frames have the scan's recorded size exactly. The article's words lie inside its boxes on them: 0.31 to 1.00 of its distinct words of five letters or more, and 0.78 at the median.
  - The `frames` run then checked each batch path's own frame. None of the 18 has the recorded size, and the article's words aren't in its boxes: 0 to 0.11.
  - The size match isn't chance. In the 15 batches that hold half of such pages, a page's neighbouring frame never has its size (0 of about 115 pairs of agreeing pages).
  - The offset is systematic, batch by batch, and mostly in `dlc_` batches. In `dlc_earl_ver02`, 1,120 of its 1,147 pages have a member frame one above the batch path's. 202 batches hold such pages, and 10 of them hold 39%.
  - **So where the two differed, the stored `service`, which `printings.py` took from the batch path, named a frame beside the article's page.** That was up to 20,643 candidates (2.5% of those with both, decision 33).
  - **The EM's call (2026-10-30), which supersedes decision 33's frame rule** (`crops.batch_path_service`, used by `printings.py`, `page_service` and `crops_for`):
    - Where only the frame differs, the page is the batch path's batch with the member's frame.
    - Where the member's reel differs too (396 candidates), the batch path's page stands. The evidence for the member is thin there: the map has the member's issue on the member's reel for only 12 of the 411 such pages, and for both sampled ones the batch path's batch holds no page at the member's place.
    - Either way, the page is checked before its crop is shown, as a page with no batch path is. A page goes unchecked only where its member and batch path agree.
  - **It changes the stored service of 20,247 candidates, on 17,545 pages in 187 batches** (`reels.json`, `frame_rule`). That's decision 33's 20,643 with another frame, less the 396 with another reel. The most are in `dlc_earl_ver02` (1,163), `dlc_dutch_ver02` (1,032), `dlc_abe_ver01` (964), `dlc_chester_ver02` (929) and `dlc_braniff_ver01` (872).
- **The page check** (`crops.page_check`), for a page located without a batch path, before its crop is shown. `crops_for` runs it, and fetches no crop for a page it rejects.
  1. The page has to exist: `info.json` answers.
  2. It has to be the scan's recorded size.
     - Where AmericanStories marks the size approximate, the size is only the extent of the boxes (decision 18), so the boxes have to lie on the page instead.
     - That's 19% of the candidates' pages with no batch path.
  3. LoC's OCR of the page, its ALTO, has to hold the article's words inside the article's boxes: at least a fifth of its distinct words of five letters or more.
     - An article with fewer than 10 such words can't be checked, and isn't shown. None in the measurement had so few.
  - The ALTO sits beside the image (`tile.loc.gov/storage-services/…/{frame}.xml`), at about 1 MB a page. The cache keeps only its words and their boxes.
- **The text rule came from calibration's 38 pages** (the 20 drawn and the 18 batch path frames):
  - The article's words anywhere on the page don't separate right from wrong: 0.37 to 1.0 on the article's page, and up to 0.5 on the frame beside it.
  - Its words inside its boxes do: 0.31 to 1.0 on its page, and 0 to 0.11 on the frame beside it. A fifth sits in the gap.
- **Measuring the check needed a truth the check doesn't decide.** The EM's design took pages whose member names another frame as wrong pages, but those turned out to be the article's pages. So the measurement (seed "2B.3 measure") instead drew:
  - 90 other candidate pages whose member and batch path agree, so two sources name the one frame: 45 of exact size and 45 approximate.
  - Each was checked on its own frame, which should pass. It was also checked on the frame beside it in its batch, one up or down at random, which should fail. The article was the same, and so was its scan's recorded size.
- **The page check's errors** (`eval/results/phase2b/page_check.json`, `summary`):
  - **False accepts: 0 of 90 (0–4.1%).** 31 of the frames beside don't exist, and of the 59 that do, the check accepts none (0–6.1%).
  - **Size alone isn't enough:**
    - It would accept 2 of the 36 exact-size frames beside that exist (5.6%, 1.5–18.1%), more than a few percent.
    - It would accept all 23 approximate ones, whose boxes fit.
    - The text check rejected all 25.
  - **False rejects: 2 of the 85 own frames that exist (2.4%, 0.6–8.2%).** That's 0 of 41 of exact size and 2 of 44 approximate.
    - Both are the article's page, by their crops, and LoC's OCR of them is garbled: "he ceptisady gifted. Be ad r p enlmto crew4de" where the article reads "…ceptionally gifted. He had performed to crowded…". The failure is the safe kind, since no crop is shown.
    - One of them, the Caledonian's 1856 letter, also has AmericanStories' stray box (decision 29): its first box is the paper's masthead.
  - 5 of the 90 own frames' batches no longer serve them (`info.json` 404s). `crops_for` sends those to loc.gov.
  - All 41 own frames of exact size have the recorded size.
  - The rule's margin: own frames' words in their boxes are 0.87 at the median, and the lowest after the two garbled ones is 0.23. The frames beside reach 0.13.
- **`page_service`** now finds a page's IIIF service in three ways:
  1. from its batch path: its batch, with the member's frame where only the frame differs;
  2. or else from its reel's first batch in the map, which asks nothing;
  3. or else from loc.gov's item for its issue.
  - The item is asked for once per issue and cached, so the issue's other pages are found without asking.
  - A page it locates without a batch path is unchecked, so crops come through `crops_for`, which checks the page.
  - A page whose member and batch path agree is shown unchecked. Where its batch has been reissued, loc.gov names its current service, at the same place.
- **The cache** (`crops.cached`): every answer from the Library of Congress is cached under `data/loc/requests/`, keyed by its URL, with its URL, retrieval date and status.
  - A 404 is cached. A server error that outlasts `get`'s retries isn't, so a later run asks again.
  - `loc.title_record` uses it too. Title records keep their own folder, and their copy of the caching code is gone.
  - `crops.SENT` counts every request `get` sends, by host, each retry included.
- **Requests: 549 in all, against the 600 planned,** all to tile.loc.gov, one at a time and at least 3.5 s apart. None failed, and they took about 37 minutes.

  | Run | Requests | Minutes |
  |---|---|---|
  | probes: `info.json` and the ALTO's place | 4 | |
  | calibrate | 77 | 6.6 |
  | frames | 36 | 2.0 |
  | measure | 326 | 20.8 |
  | look: two crops | 2 | |
  | reels | 104 | 7.0 |

  - The script spaces tile.loc.gov 3.5 s apart, as this step asked. `crops.get`'s default for image services stays 1 s (decision 29).
- **For 2D:** the check costs 2 requests and about 1 MB of ALTO download for each page it checks. At 5% reports, that's about 20,000 pages with no batch path, and about 1,000 more whose member and batch path disagree: 12 hours at 1 s a request.
  - **On disk,** the cache keeps a page's ALTO words at 187 KiB, the median of the 197 cached, so about 21,000 checks take about 4.0 GB. Gzipped, they'd take 1.3 GB (61 KB at the median). Keeping only the check's result would take almost nothing. The plan keeps it inside the 10 GB data budget.
- **The EM's calls on this step (2026-10-30):**
  - The frame rule changes, as above.
  - The page check's design change stands, and its text rule's fifth is frozen. 2D records each check's score and reason, so the numbers sheet can count rejections.
  - `scripts/load_skeleton.py` stays as it is. 3B's crops come only through `crops_for`.
  - **Request rates:** loc.gov's "Working Within Limits" page (https://www.loc.gov/apis/json-and-yaml/working-within-limits/, read 2026-10-30) gives these limits, each blocking for an hour past them:

    | Service | Requests a minute |
    |---|---|
    | the JSON/YAML API | 20 |
    | image services | 150 |
    | text services | 150 |
    | `/storage-services/` | 150 |

    - So tile.loc.gov stays at one request a second, and www.loc.gov at one in 3.5 s.
    - The page warns that under heavy load you may meet "429 status codes or HTML pages with CAPTCHAs" even below those rates.
    - So an HTML answer that isn't a 404 is busy, since every request the project makes expects JSON, XML or an image (`crops.captcha`). `get` pauses and asks again. A CAPTCHA page still there after the pauses raises `crops.Busy`, and `cached` never caches it.

**36. Reprint clusters become stories. Eval A's links stay, but a printing joins a story only by matching the story's first printing directly. That ends the chaining that joined different stories in 54 of the 207 largest clusters. Precision per candidate is 100% (97.7–100%), against eval A's 98.0%, and recall is 84.7%.**
- **What makes two printings one story:** one is the other's text printed again.
  - That allows OCR errors, cuts, a new or missing headline, a credit line, and paragraphs added or dropped at either end.
  - An advertisement or notice printed again word for word is one story too.
  - A printing held whole in a longer one is one story with it, so a notice and the column that holds it are one story.
- **What doesn't:**
  - shared boilerplate: stock phrases, an advertisement's standard wording, a legal form, a masthead
  - a quoted passage: a verse, a poem or a quotation inside otherwise different articles
  - a serial's other instalments
  - a standing column or department with other content
  - a template with other particulars, such as testimonials quoting different people
  - the same event told in different words
  - two fragments of one long text that hardly overlap, since neither printing holds the other. Merging them would leave the reader one fragment.
  - `eval/clusters/LABELLING.md` is the reading agents' version.
- **Eval A's clusters (decision 27), and what changes:**
  - Eval A joins two candidates that share a pair among their six smallest sampled seven-word runs, from their first 120 words. A pair held by more than 1,000 candidates is boilerplate.
  - It joins every linked pair, so a chain of links joins stories that share nothing. That gave v2's 91,301 clusters holding 30.3% of candidates, and 952,591 distinct stories.
  - The links stay as they are, as the blocking. The new method never joins candidates the links leave apart, so every story sits inside one of eval A's clusters. That's why an evaluation set drawn from eval A's clusters before any tuning covers every link the method can make.
- **The stories** (`paperghosts/cluster/reprints.py`, `stories`; `scripts/clusters.py`):
  1. The printings are taken earliest first, ties by article id.
  2. Each looks at the stories of the printings it is linked to.
  3. It joins the one whose first printing it matches best, where at least the threshold of the shorter's shingles are the other's. Otherwise it starts a story of its own.
  - Every member matches its story's first printing directly, so nothing chains.
  - **Shingles** (`shingles`) are five-word runs of 3+ letters in the first 600 words, one in four kept by its own hash. They are shorter than the links' seven-word runs, so they weather OCR errors better, and they cover five times as much of the text. The share is taken of the shorter printing, so a cut reprint is held whole in its original.
  - **The threshold is 0.25**, tuned on the dev set alone (`tune`, `eval/clusters/tuning.json`), with a false merge costing five false splits:

    | Threshold | 0.2 | 0.25 | 0.3 | 0.4 | 0.5 | 0.6 | 0.8 |
    |---|---|---|---|---|---|---|---|
    | False merges | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
    | False splits | 21 | 22 | 28 | 42 | 59 | 86 | 137 |
    | Cost | 31 | **22** | 28 | 42 | 59 | 86 | 137 |

    0.5 was the provisional value before any labels.
- **Stable ids:** a story's id is its first printing's article id. The same candidates give the same stories and the same ids on every run, which 2C's split by cluster needs.
- **The reader reads** each story's first printing, and also every member at least 25% longer than it, since the extra text might hold another story. That's the answer to a false merge's cost: a report merged into another story would never be read.
  - A first version read every member with less than 80% of its shingles in the first printing. That flagged OCR noise, not added text: 166,717 members, against 27,806 by length.
- **The evaluation set** (`eval/clusters/eval.json`, 667 pairs) was drawn from eval A's clusters before any label or tuning (seed "2B.4 eval"). It was then labelled and frozen, with its sha256 in `frozen.json` (`094d4070…754c`), and pushed at `f86021f` before tuning began.
  - **Per candidate, 200:** a uniform draw of clustered candidates, each paired with a random other member of its cluster. That weights precision as the reader's job and the story counts are weighted.
  - **Per cluster, 100:** a uniform draw of clusters with a random pair from each, as eval A drew them.
  - **Large clusters, 207:** every cluster of 50 printings or more (v1 had 157), with its two least similar members.
  - **Near the threshold, 80:** per-candidate pairs whose shorter printing has 20% to 60% of its shingles in the other.
  - **The body probe, 80:** pairs that share a pair of runs among their body's, from word 120, but sit in different clusters of eval A's, or in none.
  - No candidate is in two pairs, apart from the large clusters' fixed pairs.
- **The dev set** (`eval/clusters/dev.json`, 160 pairs, seed "2B.4 dev"): 40 per-candidate pairs, and 120 from 10% to 80%. None shares a candidate with the evaluation set.
- **Labelling**, by decision 30's protocol:
  - 17 reading agents read 50 pairs each, with both sets shuffled together (seed "2B.4 batches"). A batch names no set, stratum or score, and shows each printing's paper, date, headline and first 400 words.
  - **My blind re-check:** a seeded 10% of each stratum's commoner label ("same" in every stratum), judged before seeing the agents' labels. I agreed on all 61 (94.1–100%).
  - **Read in full:** every rarer label and close call, 77 in the evaluation set and dev's 4 close calls, against both printings' full texts.
    - All 43 of the agents' "different" labels stand.
    - Their 38 close calls went 15 to "same" and 23 to "different".
  - This maps decision 30's protocol onto pairs. There, the rare label, a report, was read in full. Here the rare label in every stratum is "different", so those were read in full.
- **Results, at 0.25** (`eval/results/phase2b/clusters.json`):

  | Stratum | Precision | Recall | Eval A on the same pairs |
  |---|---|---|---|
  | per candidate | 166 of 166: 100% (97.7–100%) | 166 of 196: 84.7% (79.0–89.1%) | 196 of 200 one story: 98.0% (95.0–99.2%) |
  | per cluster | 87 of 87: 100% (95.8–100%) | 87 of 100: 87.0% (79.0–92.2%) | 100 of 100 (96.3–100%) |
  | near the threshold | 65 of 65: 100% (94.4–100%) | 65 of 79: 82.3% (72.4–89.1%) | 79 of 80 |
  | large clusters' least similar pairs | 26 of 29: 89.7% (73.6–96.4%) | 26 of 153: 17.0% (11.9–23.7%) | 153 of 207: 73.9% (67.5–79.4%) |
  | body probe | none joined | 0 of 76 | none joined |

  - Eval A's recall within its own clusters is 100% by construction, since it joins every pair it links.
  - **The trade:** the method removes eval A's false merges, 4 of the 200 per-candidate pairs and 54 of the 207 large clusters' pairs. In return it splits 15% of the true reprints, mostly where OCR noise leaves too few shared runs.
  - At five to one, eval A costs 20 on the per-candidate pairs and the method 30. On the dev set, eval A costs 40 and the method 22.
    - So per candidate the two are close, and the method's gain sits in the large clusters, where the chaining is.
    - On the dev set, a hybrid that kept eval A's clusters below 20 printings would cost 24, so the method stands as it is. The eval set's numbers changed nothing.
- **Chaining in the large clusters:** 54 of the 207 least similar pairs are different stories (26.1%, 20.6–32.5%). The method splits 51 of them (94.4%, 84.9–98.1%). The 54, by kind, from the reading notes:

  | Kind | Clusters |
  |---|---|
  | a standing column or report of another day or week: markets, freight, prices, river news, church notices and directories | 15 |
  | advertisements and notices on one template with other particulars, including two ad columns that share one ad | 14 |
  | a quoted stanza, verse, epigraph or scripture inside another article | 12 |
  | a serial's other instalments, or their synopses | 5 |
  | fragments of one long text that hardly overlap | 4 |
  | unrelated texts, joined only through the chain | 3 |
  | two variants of one piece: the curse on the man who won't pay the printer | 1 |

  - They chain because eval A needs only two shared runs from the opening, and templates, standing columns and quotations share their opening wording. The links' tokens drop digits, so market reports of different days look alike.
  - **The 3 left joined** (`eval-0432`, `eval-0466`, `eval-0506`) are one pattern. Two different texts each hold a short first printing whole, such as a poem's lines, stock clairvoyant wording or a sermon's opening, so both match it. A floor on the share of the longer printing would catch them. That's for a fresh draw.
  - The ten largest clusters, before and after:

    | Printings | Stories now | Largest story | Its least similar pair | Split |
    |---|---|---|---|---|
    | 732 | 39 | 210 | different: a cotton freight table of different days | yes |
    | 684 | 9 | 515 | one story | yes, a false split |
    | 487 | 28 | 295 | one story | yes, a false split |
    | 427 | 56 | 340 | one story | yes, a false split |
    | 402 | 3 | 400 | one story | yes, a false split |
    | 379 | 15 | 332 | one story | yes, a false split |
    | 342 | 43 | 91 | different | yes |
    | 308 | 39 | 188 | one story | yes, a false split |
    | 271 | 13 | 141 | different: a steamboat's timetables of other seasons | yes |
    | 264 | 15 | 86 | one story | yes, a false split |

    The least similar pair is the hardest by construction. It shares no sampled shingles, so the method can't keep it together.
- **v2's stories:** 974,399 distinct stories, against eval A's 952,591 (+21,808, 2.3%).
  - 96,105 have more than one printing, holding 357,828 printings (28.9% of candidates), and 82,854 of those span more than one paper.
  - By size: 52,483 of 2 printings, 16,823 of 3, 8,530 of 4, 13,414 of 5 to 9, 3,915 of 10 to 19, 832 of 20 to 49, and 108 of 50 or more.
- **The reader's job** is 974,399 first printings and 27,806 longer members: 1,002,205 of 1,236,122 candidates (81.1%). Eval A, with one printing per cluster, gave 952,591.
- **The body probe: eval A's links miss many reprints.** 76 of its 80 pairs are one story: 95.0% (87.8–98.0%), all of them outside the method's reach.
  - Its frame holds 55,711 links across eval A's clusters, touching 77,641 candidates. 42,733 of those are in no cluster at all.
  - These are reprints whose openings differ, such as a new first paragraph or a cut start, or whose opening runs fell outside each other's six smallest.
  - **Proposed for the EM, not done:** add the body's links to the blocking, with the direct-match rule keeping them from chaining, and measure it on a fresh draw. Adopting it now would mean tuning on the frozen set.
- **BUDGET.md's third scenario** now takes the stories' sizes (`scripts/budget_stories.py`): 0.609 stories per printing in v1's candidates and 0.820 in those v2 added. That gives 62,402 stories at the top of the range, against 61,960, needing 461.8 MB as stored and 372.5 MB with every lever. The conclusions stand: nothing fits beside `sample_mflix`, and everything fits without it.
- **For 2C:** split gold, dev and train by story id. The reader reads each story's first printing and its longer members.
- **The EM's calls on this step (2026-10-31):**
  - **The stories stand**, as recommended. Adding the body's links to them is measured in 2D, on a fresh draw.
  - **The reader reads every triaged candidate, not the job above** (RDR-11, ARCHITECTURE 3.2). This supersedes this decision's reader rule and its "for 2C" note.
    - The skip rule would leave 233,917 printings unread, and 38,127 of them run past the 600 words the shingles see.
    - "One story" allows paragraphs added at either end, so a local paragraph or a different ending in a skipped member would never be read.
    - Stories stay the unit for display and for counts.
    - A member whose reading differs from its first printing's becomes a report of its own, shown as printed inside its story. It differs if it's a report where the first printing isn't one, or if it gives another place, date or person. 2D counts these members, and they double as false-merge candidates.
    - If 2C's Tinker credit check finds that every candidate doesn't fit, the step stops. The EM gets the shortfall, and the skip rule's loss measured on a seeded draw of skipped members read beside their first printings. That trade-off is the owner's.
  - **2C splits gold, dev and train by the most inclusive grouping, not by story id.** That's connected components over eval A's links and the body probe's 55,711 links (decision 37). Chaining only makes a split safer.
  - **A limitation, and the EM's check:** the reading agents saw 400 words of each printing.
    - 184 of the 318 pairs the stories join, in the per-candidate, per-cluster and near-threshold strata, have a printing longer than that (`scripts/clusters.py unseen`, `eval/results/phase2b/clusters_unseen.json`).
    - Where both printings run at least 50 words past it (127 pairs), the check compares the two tails' unsampled five-word runs with the openings'.
    - The EM read five low pairs: `eval-0040`, `0052`, `0217`, `0261` and `0576`. I read the four others among this ranking's lowest eight: `eval-0100`, `0251`, `0255` and `0509`.
    - All nine are one text. What lowers their tails is cuts, OCR noise, shifted article boundaries, and items glued on by segmentation. `eval-0040` is two overlapping windows of one instalment.
    - 2D's fresh draw shows its readers the full texts.
  - **For 2D: digits in the shingles,** measured on the fresh draw. `eval-0508`, ocean-freight columns a year apart, has 0.267 of the shorter's shingles in the other, above the threshold, because the tokens drop the figures that tell the two apart.
  - My calls on the hard cases stand, and so does the mapping of decision 30's protocol.

## Phase 2C (2026-10-31)

**37. The gold set is designed and drawn after `POLICY.md` and before any label: 300 gold and 150 dev articles in 17 strata, each with its inclusion weight. The most inclusive grouping and a whole-text check keep their reprints out of the training pool, and `check_leakage.py` passes. At the judged rates gold holds about 35 reports, before those of phantom sightings and hoaxes, which nothing judged measures.**

- **The order (RDR-3):** `POLICY.md` was committed at `6cd57e2`, before the draw script existed. `eval/gold/split.json` and `HASH` come after it in git history, and the split records `POLICY.md`'s sha256.
- **The grouping (the EM's call B):** `reprints.groups`.
  - It joins eval A's links, through the opening's runs, with links through the body's runs, the 120 words from word 120. Links chain through any number of printings.
  - One printing's opening and another's body share a key space, so a story printed under a new lead joins its original.
  - It covers every article gold and dev are drawn from: 1,236,122 candidates and the 310,263 articles of the near-miss reservoir.
  - 108,967 groups of two or more hold 474,805 of them, and the largest holds 1,098. 28,324 near misses join a group.
- **The whole-text check** (`scripts/check_leakage.py`, RDR-4) catches the reprints the grouping didn't link.
  - **The rule:** a pool article reprints a gold or dev article when their whole texts share at least 5 five-word runs, unsampled, and those are at least 10% of the shorter's runs.
  - **Justified on decision 36's labelled pairs** (`check_leakage.py justify`, `eval/results/phase2c/leakage_threshold.json`):

    | Set and stratum | One story, flagged | Two stories, flagged |
    |---|---|---|
    | eval, per candidate | 196 of 196 | 2 of 4 |
    | eval, per cluster | 100 of 100 | none drawn |
    | eval, near the threshold | 79 of 79 | 1 of 1 |
    | eval, body probe | 76 of 76 | 3 of 4 |
    | dev, near the threshold | 115 of 115 | 4 of 5 |
    | dev, per candidate | 37 of 37 | 2 of 3 |
    | eval, large clusters' least similar pairs | 88 of 153 | 8 of 54 |

  - The rule flags all 603 one-story pairs of the randomly drawn strata. The lowest share is 0.105 (`dev-0088`) and the fewest shared runs is 6, so the rule sits just under both.
  - The large clusters' least similar pairs are the hardest by construction, and eval A's links group them anyway.
  - It flags 12 of the 17 randomly drawn pairs of two stories, since those pairs share passages. A false flag only keeps an article out of training.
  - **It earned its place.** Outside their groups, 1,196 pool articles reprint 142 of the 450 gold and dev articles. `split.json`'s quarantine lists 1,201 flags, one per pool and held article, since 5 pool articles each reprint two held ones. Most are short repeated texts: mediums' cards and patent-medicine adverts re-run in later issues, steamer timetables, market columns, and wire passages two papers share. An advert of 50 words has about 40 seven-word runs, of which one in eight is kept, so a few OCR errors leave it without the two shared runs a link needs.
- **The strata** (`scripts/gold_draw.py`, `eval/results/phase2c/gold_draw.json`). A candidate falls in the first that fits:
  1. **Three edge-case slices** the archive holds too few of to meet by chance (SRS 7.3), found by pattern: phantom ships, trains and lights (E8), hoaxes and pranksters (E6), and text not in English (E12). The other eleven slices are common among candidates, and 2C.2 counts each slice on the labels.
  2. **Before 1850:** 2.2% of candidates. A proportional share would be about 7 of 300, too few for B8's decade slices.
  3. **Lexicon v2's five rules, rarest first,** so each rule is measured, ouija included. Then v1's terms alone. Each is split by whether a ghost term is in the headline, since that is where reports gather: 7 of the 27 judged items with one were reports, against 14 of the 373 without. The headline strata are oversampled for the reports field-level intervals need.
  - **Near misses** come from the near-miss reservoir, each year in proportion to its pool, through eval A's `draw`. Triage can then be measured on gold. Triage's idiom rule is measured on the candidates in gold it would drop.
  - Within each candidate stratum the draw is systematic in date order, so each decade gets its share, give or take one.

- **The allocation**, with the reports expected at the judged rates (the Wilson ends in brackets):

  | Stratum | Articles | Gold | Dev | Judged reports | Expected in gold |
  |---|---|---|---|---|---|
  | E8: phantom ships, trains and lights | 6,392 | 8 | 4 | 0 of 1 | 0.0 (0.0–6.3) |
  | E6: hoaxes and pranksters | 3,181 | 8 | 4 | none | not judged |
  | E12: not in English | 5,915 | 7 | 3 | 0 of 4 | 0.0 (0.0–3.4) |
  | before 1850 | 26,826 | 20 | 10 | 0 of 15 | 0.0 (0.0–4.1) |
  | ouija, term in the headline | 773 | 8 | 4 | 4 of 13 | 2.5 (1.0–4.6) |
  | ouija, none in the headline | 5,554 | 12 | 6 | 11 of 180 | 0.7 (0.4–1.3) |
  | seance, term in the headline | 3,508 | 10 | 5 | 4 of 13 | 3.1 (1.3–5.8) |
  | seance, none in the headline | 28,606 | 12 | 6 | 11 of 180 | 0.7 (0.4–1.3) |
  | spirit_phrase, term in the headline | 3,130 | 10 | 5 | 4 of 13 | 3.1 (1.3–5.8) |
  | spirit_phrase, none in the headline | 35,434 | 12 | 6 | 11 of 180 | 0.7 (0.4–1.3) |
  | spiritualism, term in the headline | 7,910 | 10 | 5 | 4 of 13 | 3.1 (1.3–5.8) |
  | spiritualism, none in the headline | 54,211 | 12 | 6 | 11 of 180 | 0.7 (0.4–1.3) |
  | spirit+medium, term in the headline | 569 | 6 | 3 | 4 of 13 | 1.8 (0.8–3.5) |
  | spirit+medium, none in the headline | 56,126 | 14 | 7 | 11 of 180 | 0.9 (0.5–1.5) |
  | v1 terms only, term in the headline | 59,176 | 80 | 40 | 3 of 14 | 17.1 (6.1–38.1) |
  | v1 terms only, none in the headline | 937,871 | 46 | 23 | 3 of 173 | 0.8 (0.3–2.3) |
  | near misses | 6,695,792 | 25 | 13 | 0 of 300 | 0.0 (0.0–0.3) |

  Articles are each stratum's size outside `POLICY.md`'s example groups. For near misses it's the near-miss pool the reservoir stands for. The five rules' rows share the rate their judged items pool.

- **Expected reports: 35.3.** That's each stratum's draw times the report rate eval A and lexicon v2 judged in it (decisions 27, 30 and 31), summed. The rules' strata pool their judged items, which are too few apart. Adding each stratum's Wilson ends gives 14.0 to 86.5, which is wider than the total's own interval.
  - E6 holds no judged item and E8 one, so the 35 counts none of their reports. Under `POLICY.md` a sighting of a phantom ship (rule 14) and an exposed hoax (rule 7) are reports.
  - The judged labels predate `POLICY.md`, and rule 2 turns one of eval A's `other` into a report.
  - **For field-level intervals:** at 35 reports, a field right in 30 of them has a Wilson interval of 71–94%. About 50 reports would take about 70 more articles in v1's headline stratum, out of the near misses, the bulk and the early decades. I kept those, since they measure triage, the bulk's kinds, and B8's early decades.
- **Decades in gold:** 22 before 1850, then 12, 15, 17, 29, 52, 50, 46 and 39 for the 1850s to the 1920s, then 9, 6, 1 and 2 for the 1930s to the 1960s.
- **Inclusion weights:** each article's `pi`, its stratum's draw over its size, and its `weight`, 1/`pi`, are in `split.json`. Gold's candidate weights sum to 1,235,182, every candidate less the 940 in `POLICY.md`'s example groups. A near miss stands for 267,832 of the near-miss pool's 6,695,792.
- **Dev:** 150 articles, gold's design at half the size, drawn from outside gold's groups. No dev article reprints a gold one by whole text, so none was redrawn.
  - **I label dev by hand under `POLICY.md`, in 2C.2, alongside gold and before any model output.** Model selection then aims at the same truth as gold, not at the teacher's labels the student learns from.
- **`POLICY.md`'s examples:** 63 articles. 60 are candidates, and they and their groups, 944 articles, are left out of gold and dev.
  - The other 3 are lexicon v1's random samples from eval A's screen, in no file the draw reads.
  - `check_leakage.py` compares all 63 with gold and dev by whole text, and none is reprinted there.
- **The pool:** 1,539,818 articles: every candidate and near-miss reservoir article outside the 6,567 held out. Those are gold, dev, their groups, the quarantine and its groups.
  - 2C.4 draws the teacher-labelled training data from the pool, at most one printing per story.
  - The random reservoir stays out of training, since eval B screens it for recall.
- **`check_leakage.py` exits 0** (`eval/results/phase2c/leakage.json`): no group crosses the split, no pool article reprints a gold or dev one, no dev article reprints a gold one, no example is drawn or reprinted, and `HASH` matches.
- **The labelling page** (`scripts/label_gold.py`) runs on 127.0.0.1 only.
  - It shows each article's OCR text beside its crops, which come through `crops_for`. A page whose member and batch path disagree is checked before its crop is shown, and a rejected page shows why.
  - `POLICY.md` is open beside the form, and its 18 rules are tick boxes.
  - Every RDR-2 field, and the kind, takes its quote from a selection in the text.
  - A label is saved only if every quote is in the text (give or take whitespace) and every choice is the schema's. Fields stay empty unless the kind is a report.
  - Each labeller keeps one label per article, so the owner's re-check sits beside mine without replacing it.
  - Articles come in a seeded shuffle, with no stratum or weight shown.
  - Tried on the first article in that order, it fetched its three crops through `crops_for` in 5 s, and they match its text. No label was saved.
  - `POLICY.md` writes `place_type`'s values with spaces, and the schema with underscores (`inn_or_hotel`). The page shows the first and saves the second.

**38. Gold and dev are labelled by hand under `POLICY.md`, all 450 through the page's `checked()`. A blind second pass relabels all of gold and a seeded fifth of dev. On gold it agrees with the first pass on 271 of 300 kinds (κ 0.88, 0.84–0.92) and on 296 of 300 report-or-not calls (κ 0.95). Every one of the 69 disagreements is ruled on under `POLICY.md`, and then ruled again blind by fresh judges, since the first rulings were the first labeller's. Every difference is settled with a written reason, all the labels and rulings are kept, and the labels are frozen by sha256 before any model output. Gold holds 46 reports, against the 35.3 expected.**

- **The first pass:** I labelled all 300 gold and 150 dev articles in batches of 20. They came in the page's seeded order, with no stratum or weight in view, and each batch was committed as it was done.
  - Every label passes `checked()`: its kind is `POLICY.md`'s, its fields are a report's only, every value has its quote in the text, and every choice is the schema's.
  - **Crops:** 443 of the 450 articles have them, cached one article at a time at loc.gov's pace. The other 7 fail the page check, or have too few words to check. I read the crop wherever the OCR was unclear. Eight dev labels were made before their crops arrived, so I read those crops afterwards and mended the labels.
- **Calls `POLICY.md` left to the labeller,** made the same way in gold and dev:
  - An apparition of the living is a report when a figure is seen, as with Buller's sight of Wolseley.
  - An essay or sermon that tells several particular claims takes its fields from the first one told in particulars. Examples: Scott's sight of the dead Byron in the Westminster Review's essay on hallucinations, and Slade's slate-writing in the Boston Pilot's round-up of exposures.
  - A column of short items under one heading is one article. Rule 16 and E11 are kept for segmentation errors: an item's tail, or an advert, joined to another.
  - E1 marks the Holy Ghost in religious matter. A joke's catechism or a pioneer tale's blazes are not E1.
  - E3 marks fiction whose plot holds a ghost, sham or real. A ghost used as a figure in a poem is not E3.
  - A place's state comes only from the text or the dateline. "Abba. la" is read as Albia, Ia., the dateline its crop shows. New York as a city gives no state.
- **The blind second pass** (`scripts/second_pass.py`) covers 330 articles: all of gold, and the 30 of dev drawn with the seed "2C.2 second pass dev sample".
  - **Eleven reading agents** each took a packet of 30, in one seeded shuffle across both splits, so no packet shows an article's split.
  - Each saw only its packet, the crops it lists, and `POLICY.md`: no first label, stratum, weight or split. Each was barred from the label files, the split, the results, the docs and git history. One reported listing two scratch folders by mistake and seeing only file names. That is fine (the EM's review): no label was in view.
  - A usage limit stopped seven of them partway, and each was resumed in its own blind context.
  - Each agent checked its labels against its packet's texts alone. Then all 330 went through `checked()` into `eval/gold/second_pass.jsonl`, never into the label files the evals read.
- **Agreement, before any ruling** (`eval/results/phase2c/agreement.json`). Rates come with Wilson intervals, and κ with a bootstrap of 2,000 resamples:

  | | Articles | Kind | κ on kind | Report or not | κ on report |
  |---|---|---|---|---|---|
  | gold | 300 | 271 (86.5–93.2%) | 0.88 (0.84–0.92) | 296 (96.6–99.5%) | 0.95 (0.89–0.99) |
  | dev sample | 30 | 25 (66–93%) | 0.79 (0.61–0.95) | 30 (89–100%) | 1.00 |
  | both | 330 | 296 (86–93%) | 0.87 (0.83–0.91) | 326 (96.9–99.5%) | 0.95 (0.90–0.99) |

  - **On the 45 gold articles both passes call reports,** each field agrees:
    - outcome 43 (85–99%)
    - place_state 42 (82–98%)
    - precision 40 (77–95%)
    - place, specific place and place type 39 each (74–94%)
    - seen 37 (69–91%)
    - people 26 (43–71%)

    The dev sample has 4 such reports.
  - **When a field agrees:**
    - Both passes leave it empty.
    - Outcome, place_type, precision and place_state: the same value.
    - Place, seen and the specific place: quotes that overlap in the text, or the same value.
    - People: each person's quote overlaps one of the other pass's, both ways.
  - **People is the loosest field.** Most of its disagreements are a person one pass adds who didn't see or claim anything: a reporter, an editor, or a crowd told of it afterwards.
- **The first rulings** (`eval/gold/adjudication.jsonl`), the first labeller's: 69 articles disagreed, 61 of them in gold. 34 were on kind, and 35 on fields alone.
  - Each ruling went through `checked()` and replaced its article's label. The record keeps the first pass's label, the second's, the ruling and its reason.
  - 58 uphold the first pass, 6 take the second's call, and 5 mend fields.
  - **16 of the 34 kind disagreements were one question:** spirit or medium in an ordinary sense, "in good spirits" or "an advertising medium". The first pass called these `other`, the second `idiom`. The ruling is `other`, since `POLICY.md`'s idioms are figures about ghosts.
  - **The second pass's call was taken six times:**
    - Basingstoke's haunted clock, a report told with a closing quip (rule 8), which makes gold's 46th report
    - a spiritualist society's display notice, an advert
    - a puff for the paper's own Sunday story, an advert
    - a camp meeting's "séance behind the woodshed", a figure for a whipping
    - spiritualists on cremation in a Catholic note, `other`
    - a stated house as a place type
  - **Fields were emptied where a value wasn't stated:** "claimed to be haunted" states nothing seen, and a clerk's workplace isn't where his sittings were.
  - **`POLICY.md` version 3,** dated, adds the two clarifications the rulings settled, which every label already follows. Spirit or medium in an ordinary sense is `other` (rule 10), and a display notice of meetings and messages is an advert (rule 12).
- **The blind re-ruling** (the EM's review: gold can't rest on a judge ruling its own case). Four fresh judges ruled all 69 disputes again, one pair at a time (`scripts/blind_rulings.py`).
  - **What each judge saw:** `POLICY.md` v3, the article and its crops, and the two labels as A and B, by a seeded coin with no labeller, note or ruling. The judges were barred from every label file and from the A/B key.
  - **Against the first labeller's rulings** (`eval/results/phase2c/blind_rulings.json`), with Wilson intervals:

    | | Same ruling | Interval | The blind ruling sides with: first, second, neither |
    |---|---|---|---|
    | kind | 28 of 34 | 66–92% | 25, 9, 0 |
    | seen | 5 of 10 | 24–76% | 3, 7, 0 |
    | people | 4 of 19 | 9–43% | 3, 12, 4 |
    | place | 4 of 7 | 25–84% | 3, 4, 0 |
    | specific place | 2 of 6 | 10–70% | 1, 5, 0 |
    | place type | 4 of 6 | 30–90% | 2, 4, 0 |
    | precision | 2 of 5 | 12–77% | 1, 4, 0 |
    | place state | 2 of 3 | 21–94% | 2, 1, 0 |
    | outcome | 1 of 2 | 9–91% | 1, 1, 0 |

  - **The first labeller's field rulings leaned toward its own labels.** On kinds the blind judges mostly agree with the first rulings. On fields they side with the second pass two to one, and on people four to one.
  - **Settling:** 30 articles' blind rulings differ. I re-read each with its crop, and took the blind ruling unless the text or another label gave a written reason against it. That took the blind ruling in 28 and kept mine in 2, each for consistency with labels no one disputed:
    - an obituary's "spirit land" stays `other`, as two other gold obituaries are in both passes
    - the second printing of the backwoods-preacher sketch stays `fiction`, as the judge ruled its other printing
  - `adjudication.jsonl` keeps, for each dispute, the first label, the second, the first labeller's ruling (`own_ruling` where it changed), the blind ruling, and how it was settled.
  - **Four kinds changed:**
    - the camp meeting is `religious`: the whipping figure doesn't set the article's kind
    - the mumps "knocking" is `other`, since it isn't a ghost figure
    - the Russian-news ouija simile is an `idiom`
    - an amusements column with seats on sale is an advert
  - The other 24 changes are to fields, mostly people: the blind rulings drop a person told of it afterwards and add a stated claimant, such as an editor who claims spirit control.
  - **Rule 10's clarification, checked:** on the 17 other-versus-idiom disputes, the judges would rule `other` on 15 even without v3's bullet, and they call the bullet right in all 17. The two exceptions: "bold spirits", which they rule `other` under the bullet, and the obituary's "spirit land", kept as above.
  - **Final, all 69:** kinds side with the first pass in 27 and the second in 7. Gold still holds 46 reports.
- **The freeze** (`1e64421`, re-frozen after the blind re-ruling):
  - `eval/gold/HASH` lists the sha256 of `labels.jsonl` and `dev_labels.jsonl` beside `split.json`'s, committed before any model output.
  - The two files hold exactly 300 and 150 labels, one per article. Each is the first pass's label where the passes agreed, and the ruling where they didn't. All pass `checked()` (`second_pass.py frozen`).
  - `check_leakage.py` now checks every file `HASH` lists.
  - Gold's final kinds: 46 reports, 89 other, 66 fiction, 58 idiom, 31 adverts, 10 religious. Dev's: 32 reports, 44 other, 30 fiction, 27 idiom, 10 adverts, 7 religious.
- **Gold's reports by stratum** (`eval/results/phase2c/gold_measures.json`), against the draw's expectation:

  | Stratum | Gold | Reports | Expected |
  |---|---|---|---|
  | E8: phantom ships, trains and lights | 8 | 0 | 0.0 (0.0–6.3) |
  | E6: hoaxes and pranksters | 8 | 3 | not judged |
  | E12: not in English | 7 | 0 | 0.0 (0.0–3.4) |
  | before 1850 | 20 | 0 | 0.0 (0.0–4.1) |
  | ouija, term in the headline | 8 | 2 | 2.5 (1.0–4.6) |
  | ouija, none in the headline | 12 | 0 | 0.7 (0.4–1.3) |
  | seance, term in the headline | 10 | 2 | 3.1 (1.3–5.8) |
  | seance, none in the headline | 12 | 1 | 0.7 (0.4–1.3) |
  | spirit_phrase, term in the headline | 10 | 7 | 3.1 (1.3–5.8) |
  | spirit_phrase, none in the headline | 12 | 3 | 0.7 (0.4–1.3) |
  | spiritualism, term in the headline | 10 | 1 | 3.1 (1.3–5.8) |
  | spiritualism, none in the headline | 12 | 1 | 0.7 (0.4–1.3) |
  | spirit+medium, term in the headline | 6 | 4 | 1.8 (0.8–3.5) |
  | spirit+medium, none in the headline | 14 | 0 | 0.9 (0.5–1.5) |
  | v1 terms only, term in the headline | 80 | 20 | 17.1 (6.1–38.1) |
  | v1 terms only, none in the headline | 46 | 2 | 0.8 (0.3–2.3) |
  | near misses | 25 | 0 | 0.0 (0.0–0.3) |
  | **all** | **300** | **46** | **35.3 (14.0–86.5)** |

  - The 46 sit inside the expected range, above its centre.
  - E6, which nothing judged, adds 3.
  - The rules' headline strata hold 16 against about 13.6 expected, and the low-rate rule strata 5 against about 3.7.
  - At 46 reports, a field right in 39 of them has a Wilson interval of about 72–92%.
- **The weighted report rate** (Σ weight × report / Σ weight, over candidates and near misses): 0.97%, with a stratified bootstrap interval of 0.38–1.81%.
- **The story-place rule, as code** (`gold_measures.story_state`), was written and tested before the freeze and run once after it.
  - It takes a state named after a comma in the place's quote. Else, a town from the quote named elsewhere with a state after a comma. Else, the dateline's state. It never takes the paper's state.
  - On gold's 32 reports with a place, it agrees with the labelled `place_state` on 29 (76–97%): 6 the same state, 23 both empty.
  - It never gives a wrong state. Its 3 misses are states the OCR prints after a period ("Allentown. Pa", "Springfield. Ohio") or apart from the place's quote (Georgia).
  - **The paper's state**, decision 34's fallback, matches only 2 of the 9 labelled states (6–55%).
- **Slices on the frozen labels, gold then dev:**

  | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | E9 | E10 | E11 | E12 | E13 | E14 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | 3, 4 | 34, 15 | 32, 9 | 11, 2 | 30, 26 | 12, 3 | 23, 9 | 8, 5 | 115, 44 | 12, 9 | 9, 3 | 7, 3 | 1, 1 | 21, 9 |

  - E9 comes from the grouping: 159 of the 450 are in a group of two or more.
  - E1 and E13 are too thin to measure alone.
- **The grouping missed one reprint within gold:** the comic sketch of a backwoods preacher is printed twice in gold. Two printings within gold don't leak into training, and both are labelled `fiction`.
