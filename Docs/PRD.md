# PRD: Paper Ghosts

What we are building, for whom, and how we'll know it worked. The full spec is `BRIEF.md`; this file is the product view of it.

## 1. Summary
Type a town and read the ghost reports that America's newspapers actually printed there between 1774 and 1963. Each one comes with the original clipping, what happened next, and sometimes the real person behind the ghost.

Paper Ghosts never writes a ghost story. Everything it shows was printed in a newspaper, and every claim links to the clipping it came from.

## 2. The problem
- Real reports are buried in 340 GB of scanned pages that nobody can search by town.
- People get web legends and ghost-tour retellings instead, and those drift from what was printed.
- The old Chronicling America JSON API is gone (it returns 404). The archives that remain show pages, not stories.

## 3. Who it's for
| Person | What they want |
|---|---|
| A curious local, on Halloween, on a phone (primary) | "What did the papers say about ghosts in my town?" |
| A local historian or genealogist | The original source and its follow-ups, with dates and papers, so they can cite it |
| A ghost-tour guide | What the 1890s paper actually said, next to what the tour says now |
| A hackathon judge | Proof that it is real, that it works, that the writing is good, and that open models do the real work |

## 4. Goals and non-goals
**Goals**
1. Every US town with a printed report is searchable and returns real clippings.
2. Every fact on screen carries a quote from its clipping that code has verified.
3. A small open model trained on Tinker reads the whole archive, with measured accuracy compared against a large teacher and a measured cost per 10,000 articles.
4. The top cases get case files: follow-ups, debunkings, the person behind the ghost, and then and now.
5. It feels like a newspaper morgue after hours (`UI-IDEAS.md`), and it is fast on a phone with the lights on or off.

**Non-goals**
- Generated stories, AI narration, or invented content anywhere, including screenshots.
- Accounts, logins, leaderboards or social features.
- Non-US papers. The lexicon is English, so reports in German, Spanish or other languages are missed; the "What it can't do" section says so.
- Guesses about causes of death. Private homes as walk stops.

## 5. Features
**P0: the vertical slice (must ship)**
| ID | Feature | Done when |
|---|---|---|
| F1 | Town search on a library request slip, leading to the town's drawer: envelopes with typed labels and outcome stamps, a count line, and a small map | A real town returns its real reports, and a town without any says so plainly |
| F2 | Case page: the clipping under the lamp, the transcription, a raw-OCR toggle, a typed facts card (verified quote or "not stated"), the Library of Congress source link, and **-30-** | Every field on the page traces to a quote in that clipping |
| F3 | Front page: masthead, search, **Printed on this night** and a ticker of real headlines | Works for any date of the year |
| F4 | The reel: ghost reports per million articles by year and by state, drawn like an 1870s statistical atlas | Every number comes from the eval A script |
| F5 | Lights on and off (the pull-chain), phone-first layouts, reduced motion | Passes the checks in `SRS.md` (NFR-A11Y, NFR-PERF) |
| F6 | The method page: how the archive was read, what it can't do, and the credits the licences require | Credits AmericanStories (CC-BY-4.0), GeoNames (CC-BY), the LoC scans, the map tiles, the fonts and React Bits |

**P1: depth**
| ID | Feature |
|---|---|
| F7 | What happened next: the follow-up clippings on a case page |
| F8 | The person behind the ghost: the death notice clipped beside the report, with how sure the link is |
| F9 | Then and now: today's web claims beside the original report, each with its source and retrieval date |
| F10 | Archive text search with fuzzy matching for OCR errors, where a misread spelling visibly resolves into the word it matched |
| F11 | Ghosts like this one (vector search) |
| F12 | Near me: location rounded to about 1 km, used once, never logged |

**P2:** F13 Walks: self-guided, public stops only, printable. The owner decides at the Phase 4 gate whether it's built.

**P3:** F14 Road trips, which is the first thing to cut. Optional sound, off by default.

## 6. Success metrics
Every result comes from a script in the repo. The targets below are goals; whatever the eval actually says is what gets reported.

| Area | Metric | Goal |
|---|---|---|
| Coverage | Year files read out of 180 | All 180, or each failure listed with its reason |
| Prefilter | Recall, measured on a random sample and a near-miss pool | Reported with a 95% interval or upper bound |
| Reader | Report-detection F1 and kind accuracy: tuned 4B against base 4B and the teacher | A clear win over base 4B, with 95% intervals that don't overlap |
| Reader | Cost per 10,000 articles and latency | Measured for all three models |
| Grounding | Share of displayed fields with a verified quote | 100%, by construction, plus an audit |
| Investigations | Case files written, named deaths found, cases explained or exposed, then-and-now differences | 30–60 case files; the other counts are whatever is found |
| Durability | Kill tests on the ingest and on an investigation | Both resume; no completed paid call is repeated, and any call in flight at the kill is counted |
| App | Core Web Vitals on a mid-range phone | LCP under 2.5 s, CLS under 0.1, INP under 200 ms |
| App | Accessibility | No serious axe violations; reading text contrast of at least 4.5:1 in both modes |

## 7. How it fits the challenge
**Judging criteria**
- **Writing quality (weighted most):** the DEV post is a deliverable with its own gate in Phase 5. It is written in the archive librarian's voice and built around the strongest real case the investigator finds. Every number in it comes from the numbers sheet.
- **Relevance:**
  - Spooky: real ghost reports.
  - Honouring the past, in the spirit of Día de los Muertos: the real people behind the ghosts, remembered from their own papers.
  - Open-weight models do all the reading and investigating.
- **Creativity:** the newspaper-morgue framing, the person behind the ghost, and then and now (how legends drift from what was printed).
- **Technical execution:** a full read of 340 GB, durable runs on Temporal, distillation on Tinker with honest evals, and quotes that code verifies.
- **Partner technology:** each tool has one real job and a piece of proof (`BRIEF.md` "Stack").

**The four open-angle questions the post answers**
- **Does it work with the lights and the internet off?** The reader and the investigator run on open weights on the owner's machine, and walks print to paper.
- **Does it keep things private?** There are no accounts, and near me is rounded and never logged.
- **Is it free of a service that might disappear?** The data is CC-BY text and public-domain scans, the models are open weights, and crops for the top cases are cached.
- **Where did open beat closed?** Eval B (cost per 10,000 articles, accuracy gap) and the Gemma against Ultramarine comparison answer it, whichever way the numbers go.

**Prize categories:** list only those genuinely used at submission time. Tinker is the main one (featured), then Render (featured), Gemma (featured, if the investigator's default stays Gemma 4), MongoDB Atlas, Temporal, Sentry Agent Tracing, SerpApi, Ultramarine and Entire. One win per person, so the depth goes into Tinker.

## 8. Product rules
- **The voice:** the archive's librarian, plain, dry and exact. No puns, no "spooky", no "unleash", no "dive in".
- **Respect the dead:** see `BRIEF.md`, non-negotiable 4.
- **The Halloween look:** it comes from the reading room after dark (the lamp, the lights off, the scans), as `UI-IDEAS.md` describes. No pumpkins, bats, skulls or costume-shop type.

## 9. Release plan
1. **Walking skeleton (Phase 1):** one real 1850 clipping goes all the way from the archive through Atlas and the API to a web page.
2. **Each phase deepens its layer** and ends at a gate (`BUILD-PLAN.md`).
3. **Owner gates, each needing a yes:**
   - the Render deploy, and the Atlas network-access change it needs
   - making the repo public, which the DEV template's GitHub embed requires, and which comes after the Entire session secret scan
   - publishing the DEV post
   - any spending beyond free tiers and existing credits

## 10. Open questions for the owner
- **Render plan:** free services sleep after a short idle. The static-first core path covers that, so the free plan is the recommendation. A paid instance would only speed up the live search features.
- **Walks:** the build-or-cut call at the Phase 4 gate.
