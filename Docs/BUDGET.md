# Storage budget: Atlas M0

Measured on 2026-10-30 by `scripts/budget_probe.py`, which writes `eval/results/phase2b/budget.json`. Every number here comes from that file or follows from it by arithmetic. The documents are the final 2B.1 models (decision 33). Atlas M0 is the free tier, so nothing here costs money.

## What Atlas counts against the cap

- **The cap:** M0's storage is 0.5 GB, a hard limit. The cluster comparison writes it as "Storage (Data Size + Index Size) 512 MB". That is the documents' uncompressed BSON plus their B-tree indexes ([Free Cluster Limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/), [Manage Clusters](https://www.mongodb.com/docs/atlas/manage-clusters/)).
- **How it's measured:** "Atlas calculates allocated storage using metrics returned by the dbStats command" ([FAQ: Storage](https://www.mongodb.com/docs/atlas/reference/faq/storage/)).
- **Search indexes:**
  - Atlas Search and Vector Search indexes aren't in `dbStats`.
  - Free clusters have no Search index size metrics ([Review Search Metrics](https://www.mongodb.com/docs/atlas/review-atlas-search-metrics/)).
  - So by the docs, Search indexes don't count against the cap. No page says so outright, though, and M0 can't measure them, so the budget leaves them out and keeps some headroom.
  - The cap of three Search indexes counts the whole cluster ([Search limitations](https://www.mongodb.com/docs/atlas/atlas-search/limitations/)).
- **The figure used:** the budget plans against 500,000,000 bytes, the stricter of the two readings. Reading the cap as 512 MiB would add 36.9 MB.

## Free space now

| Database | Data | Indexes | Counted | On disk |
|---|---|---|---|---|
| `sample_mflix` | 129.1 MB | 19.8 MB | **148.9 MB** | 239.2 MB |
| `paperghosts` | 0.003 MB | 0.6 MB | 0.6 MB | 11.3 MB |
| `cubby` (not this project's) | 0.0002 MB | 0.02 MB | 0.02 MB | 0.06 MB |

- **Free:** 350.5 MB with `sample_mflix`, and 499.4 MB without it.
- **`sample_mflix`:** its 239 MB on disk is compressed storage. Atlas counts 148.9 MB of it, its data plus its indexes.
- **`paperghosts`:** the 0.6 MB is the plan's empty indexes, which kept the pages the early probe runs used.

## Bytes per story

Two samples are built as full `reports` documents:
- **Text and printings:** real text, and every printing in the story's reprint cluster.
- **Embedding:** a float32 BinData vector.
- **Reader fields:** quotes that are real sentences of the article.

The samples:
- **The 1,000:** a seeded 1,000 of v2's candidates (seed "2B budget probe"). They make 1,000 stories with 5,116 printings. 29% have more than one printing, and the largest cluster has 487.
- **The judged reports:** the 24 of the 25 judged so far that v2 makes candidates.
  - These are eval A's 7, 3 of the screen's 4, and 2A.8's 14. The fourth of the screen's, the 1918 scout, isn't a v2 candidate, so it would never be stored.
  - They make 24 stories with 88 printings. 33% have more than one, and the most is 30.

| Part (mean bytes) | The 1,000 | Judged reports |
|---|---|---|
| text | 2,555 | 1,891 |
| headline and display headline | 102 | 125 |
| printings, apart from their boxes | 1,801 | 1,287 |
| printings' `bbox_list` | 502 | 395 |
| reader fields | 1,335 | 1,330 |
| embedding (float32) | 1,554 | 1,554 |
| the rest: ids, dates, place, versions, terms | 637 | 648 |
| **whole document** | **8,486** (median 6,995) | **7,230** (median 6,579) |

- **The reports are shorter than candidates in general,** with 1,891 bytes of text against 2,555, and reprinted about as often.
- **The budget takes each figure from whichever sample has more:**
  - a story's own bytes, without its printings, from the 1,000: 6,199
  - each printing's bytes from the reports: 454
- **Atlas's own sizes:** the 1,000 were loaded 500 at a time into a scratch collection with the reports validator and indexes, and it was dropped afterwards.
  - Data size is exactly the BSON bytes: 8,486,116.
  - The B-tree indexes take 401 bytes per story at 1,000, and 508 per story between 500 and 1,000. The budget uses 508.

## The levers

The size of the top of the range, 57,744 stories with 95,203 printings, as each lever changes it:

| Variant | Mean bytes, the 1,000 | Mean bytes, reports | Top of the range | Change |
|---|---|---|---|---|
| **As stored:** rule 6's levers on, float32 | 8,486 | 7,230 | 430.5 MB | |
| Rule 6 off: embedding as an array of doubles | 11,830 | 10,574 | 623.6 MB | +193.1 MB |
| Rule 6 off: crop URLs stored | 10,361 | 8,728 | 469.4 MB | +38.9 MB |
| Rule 6 off: printings with their own text | 19,612 | 11,811 | 636.9 MB | +206.3 MB |
| `bbox_list` as int16 BinData | 8,150 | 6,960 | 423.6 MB | −6.9 MB |
| `bbox_list` as int32 BinData | 8,234 | 7,028 | 425.3 MB | −5.2 MB |
| Paper, place and state in a title lookup by LCCN | 8,067 | 6,946 | 423.5 MB | −7.0 MB |
| `display_headline` derived at read time | 8,432 | 7,164 | 427.4 MB | −3.1 MB |
| int8 embedding | 7,334 | 6,078 | 364.0 MB | −66.5 MB |
| **The three:** int16 boxes, title lookup, derived headline | 7,676 | 6,611 | 413.4 MB | −17.1 MB |
| **The three, with int8** | 6,524 | 5,459 | 346.9 MB | −83.7 MB |

- **Boxes:** the largest box coordinate in either sample is 12,274, so int16 holds every box. The boxes would be unpacked when read.
- **Title lookup:** it has 3,336 LCCNs and takes 0.35 MB, which its rows include. Its place would add a little more once 2B.2's parser fills it in.
- **The three lossless levers** together save only 17 MB. The int8 embedding saves 66.5 MB, but it's lossy, and 2D has to check its neighbours against float32's on real embeddings first (`BUILD-PLAN.md`).

## How many stories fit with full text

The top of decisions 30 and 31's intervals is 74,027 + 21,176 = **95,203 report printings**. Two scenarios:
- **v1's ratio** of 22,300 stories to 36,766 printings (decision 27) gives 57,744 stories.
- **The worst case** is one story per printing: 95,203 stories.

| Variant | Scenario | Needs | Fits with `sample_mflix` (350.5 MB) | Fits without it (499.4 MB) | Stories that fit, with / without |
|---|---|---|---|---|---|
| As stored | v1's ratio | 430.5 MB | no | **yes** | 47,007 / 66,975 |
| As stored | one story per printing | 681.8 MB | no | no | 48,941 / 69,732 |
| int8 embedding | v1's ratio | 364.0 MB | no | yes | 55,597 / 79,215 |
| int8 embedding | one story per printing | 572.1 MB | no | no | 58,324 / 83,100 |
| The three | v1's ratio | 413.4 MB | no | yes | 48,947 / 69,761 |
| The three | one story per printing | 662.6 MB | no | no | 50,333 / 71,737 |
| The three, with int8 | v1's ratio | 346.9 MB | yes, with 3.6 MB to spare | yes | 58,343 / 83,152 |
| The three, with int8 | one story per printing | 552.9 MB | no | no | 60,323 / 85,974 |

At the point estimates, the needs are much smaller: 36,766 + 12,996 = 49,762 printings, so 30,183 stories at v1's ratio.

| Variant | v1's ratio | One story per printing |
|---|---|---|
| As stored | 225.0 MB: fits either way | 356.4 MB: fits only without `sample_mflix` |
| The three | 216.3 MB: fits either way | 346.5 MB: fits either way |

**Not in these figures:**
- **Places, cases and stats.** They aren't built yet, but they are small. The tests' example documents are 251 bytes for a place, 272 for a stat and 1,774 for a case. So even 20,000 places, with their 2dsphere index, take a few MB.
- **The Search indexes.** See "What Atlas counts against the cap".

## Options for the owner

At the top of the range, the full text fits on M0 only without `sample_mflix`, or with every lever including int8 and 1% to spare. In the worst case of one story per printing, it doesn't fit on M0 at all. Every option keeps the text and the search whole.

1. **Drop `sample_mflix`.** It's free, and it frees 148.9 MB and the third Search slot that `places_search` waits for. Then the top of the range at v1's ratio fits as stored. The owner's call.
2. **Take the three lossless levers:** int16 boxes, the title lookup, and the derived headline. They save 17 MB at the top of the range. int8 saves 66.5 MB more, but only after 2D's check of its neighbours on real embeddings.
3. **Size from the reader's real count.** The reader's full pass (2C) comes before the load (2D), and it gives the real number of reports and stories. At the point estimates, everything fits even with `sample_mflix`, so options 1 and 4 can wait for that count.
4. **A paid tier**, such as Flex or a dedicated M10, if the real count needs more than M0 can hold. It costs money, so it needs the owner's yes.
