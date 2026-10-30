"""Eval A over an archive read: eval/results/eval_a.json and eval/results/eval_a/ for lexicon
v1's read, which `make eval-v1` reproduces from data/archive/lexicon-v1, and
eval/results/eval_a_{version}.json and its folder for a later read in data/, which `make eval`
writes. Pass the data folder; it defaults to data/.

1. EDA: by year, by state and by term; candidate lengths; OCR quality, as the share of words
   /usr/share/dict/words knows; reprint clusters among the candidates; and the candidates
   whose scan has no batch path, which can show a clipping only if loc.gov lists the page.
2. Composition: 200 candidates at random, each put in a category by hand in
   composition.json. The categories are defined in decision 27.
3. Recall: 300 articles from the near-miss reservoirs and 300 from the random ones, each
   weighted by its year's share of the pool, marked by hand in recall.json.
4. The screen: 38,600 more from the random reservoirs, of which only those holding a flag
   word or near-miss term are marked by hand, in screen.json. Decision 30 has the method.

Every sample is seeded, so a rerun draws the same articles and keeps the judgments made. The
samples, 2 to 4, are lexicon v1's record (decision 31), so a later read gets the EDA alone.
"""

import itertools
import json
import random
import re
import sys
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import zstandard
from charts import draw_all

from paperghosts.cluster.reprints import clusters, keys
from paperghosts.ingest import lexicon
from paperghosts.ingest.crops import BATCH_PATH
from paperghosts.ingest.prefilter import SAMPLE_SIZE
from paperghosts.ingest.year import sha256
from paperghosts.stats import wilson

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "eval" / "results"
DICTIONARY = Path("/usr/share/dict/words")
OCR_ONE_IN = 20  # OCR quality is measured on one candidate in twenty, chosen by its id
COMPOSITION, RECALL, REPRINT_CHECK = 200, 300, 20
# with no report among them, the bound on missed reports is about the 36,800 found
SCREEN = 38_600
CATEGORIES = (
    "ghost_report",
    "fiction",
    "religious",
    "figurative",
    "name_or_title",
    "social_event",
    "other",
)
WORD = re.compile(r"[a-z]{3,}")
# common endings, tried in turn when a word isn't in the list as it stands
ENDINGS = (
    ("ies", "y"),
    ("ied", "y"),
    ("ing", "e"),
    ("ing", ""),
    ("ed", "e"),
    ("ed", ""),
    ("es", ""),
    ("s", ""),
    ("ly", ""),
)
# words to look around in a random-pool article, besides its opening; a guide to reading
FLAGS = re.compile(
    r"\b(?:spirit|spectral|unearthly|uncanny|weird|supernatural|seance|apparit|phantasm"
    r"|spook|wraith|goblin|banshee|witch|hoodoo|voodoo|superstiti|haint|bogey|boogey"
    r"|corpse|graveyard|midnight|in white|strange (?:noise|light|sound)|mysterious|knock"
    r"|rapp|haunt|spectre|specter|phantom|[gq][hbk]?[o0ae][a-z]?sts?\b)\w*",
    re.IGNORECASE,
)
_words = None


def flagged(text):
    """The flag words and near-miss terms in the text, which the screen reads for. Line-break
    hyphens are joined first, as the lexicon does."""
    text = text.replace("-\n", "")
    found = {" ".join(m.group().lower().split()) for m in FLAGS.finditer(text)}
    return sorted(found.union(*lexicon.near_miss_terms(text).values()))


def dictionary():
    global _words
    if _words is None:
        _words = frozenset(
            w.strip().lower() for w in DICTIONARY.read_text().splitlines()
        )
    return _words


def known(word, words):
    if word in words:
        return True
    return any(
        len(word) > len(end) + 2
        and word.endswith(end)
        and word[: -len(end)] + back in words
        for end, back in ENDINGS
    )


def ocr_quality(text, words, least=20):
    """The share of the article's words of three letters or more that the dictionary knows,
    once line-break hyphens are joined and common endings come off; None under `least`."""
    found = WORD.findall((text or "").replace("-\n", "").lower())
    if len(found) < least:
        return None
    return sum(known(word, words) for word in found) / len(found)


def draw(pools, sizes, n, seed):
    """n (year, item) pairs, each year drawn in proportion to its share of the pool across the
    archive, so the sample stands for every article in the pool rather than for each year
    equally. pools maps a year to its reservoir, and sizes to the pool's full size. A year
    whose reservoir is smaller than its share fails the draw, since shrinking that share
    would under-sample the year."""
    rng = random.Random(seed)
    years = sorted(year for year in pools if sizes.get(year) and pools[year])
    wanted = Counter(rng.choices(years, weights=[sizes[year] for year in years], k=n))
    short = {y: (wanted[y], len(pools[y])) for y in years if wanted[y] > len(pools[y])}
    assert not short, f"years whose reservoir is short, as (wanted, held): {short}"
    return [
        (year, item)
        for year in years
        for item in rng.sample(list(pools[year]), wanted[year])
    ]


def random_picks(others):
    """Eval A's 300 recall picks from the random reservoirs, what each year's reservoir holds
    besides them, and the screen's 38,600 picks from that (decision 30). others maps a year to
    its non-candidates."""
    reservoirs = {y: range(min(SAMPLE_SIZE, n)) for y, n in others.items()}
    rand, screen = defaultdict(set), defaultdict(set)
    for year, index in draw(reservoirs, others, RECALL, "eval A recall random"):
        rand[year].add(index)
    held = {y: [i for i in reservoirs[y] if i not in rand[y]] for y in reservoirs}
    for year, index in draw(held, others, SCREEN, "eval A screen"):
        screen[year].add(index)
    return rand, held, screen


def uniform(counts, n, seed):
    """n (year, index) pairs without replacement, every candidate equally likely."""
    rng = random.Random(seed)
    years = sorted(counts)
    picks = []
    for left in sorted(rng.sample(range(sum(counts.values())), n)):
        for year in years:
            if left < counts[year]:
                picks.append((year, left))
                break
            left -= counts[year]
    return picks


def window(text, position, width=320):
    start = max(0, position - width // 2)
    return " ".join(text[start : start + width].split())


def for_reading(row, year, text, spots, most=4):
    """A sampled article as it is judged: its opening, and the text around the spots."""
    return {
        "article_id": row["article_id"],
        "year": year,
        "date": row["date"],
        "paper": row["paper"],
        "headline": " / ".join((row["headline"] or "").split("\n"))[:200],
        "near_miss_terms": sorted(row["near_miss_terms"]),
        "words": len(text.split()),
        "opening": " ".join(text[:420].split()),
        "contexts": [window(text, p, 300) for p in sorted(set(spots))[:most] if p >= 0],
    }


def first_match(text, forms):
    low = text.lower()
    found = [low.find(form.lower()) for form in forms]
    return min([p for p in found if p >= 0], default=0)


def year_pass(job):
    """One year's candidates: per-article length, OCR quality for a fixed sample, reprint keys,
    paper and opening; plus the composition, recall and screen picks that fall in this year."""
    data, year, wanted, near, rand, screen, terms = job
    words, docs, picked, no_batch_path = dictionary(), [], [], 0
    # the read's own ghost terms, so v1's candidates are masked by lexicon v1
    mask = lexicon.matcher({term: lexicon.GHOST[term] for term in terms})
    with zstandard.open(data / "candidates" / f"{year}.jsonl.zst", "rt") as rows:
        for index, row in enumerate(map(json.loads, rows)):
            text = row["text"] or ""
            no_batch_path += not BATCH_PATH.search(
                (row.get("scan") or {}).get("raw_data_loc") or ""
            )
            quality = None
            if zlib.crc32(row["article_id"].encode()) % OCR_ONE_IN == 0:
                quality = ocr_quality(text, words)
            docs.append(
                (
                    len(text.split()),
                    quality,
                    tuple(keys(text)),
                    row["lccn"],
                    row["article_id"],
                    f"{row['paper'] or '?'} {row['date']}: {' '.join(text[:200].split())}",
                )
            )
            if index in wanted:
                both = f"{row['headline'] or ''}\n{text}"
                forms = [form for found in row["terms"].values() for form in found]
                picked.append(
                    {
                        "article_id": row["article_id"],
                        "year": year,
                        "date": row["date"],
                        "paper": row["paper"],
                        "state": row["state"],
                        "terms": sorted(row["terms"]),
                        "words": len(text.split()),
                        "headline": " / ".join((row["headline"] or "").split("\n"))[
                            :200
                        ],
                        "context": window(both, first_match(both, forms), 600),
                        # what the screen would still find had the lexicon missed it
                        "flags_without_terms": flagged(
                            mask.sub("▒", both.replace("-\n", ""))
                        ),
                        "category": None,
                        "note": None,
                    }
                )
    recalled, screened, tally = [], [], Counter()
    if near or rand or screen:
        seen = Counter()
        with zstandard.open(data / "samples" / f"{year}.jsonl.zst", "rt") as rows:
            for row in map(json.loads, rows):
                pool, index = row["sample"], seen[row["sample"]]
                seen[pool] += 1
                if pool == "random" and index in screen:
                    tally["drawn"] += 1
                    tally["near_miss"] += bool(row["near_miss_terms"])
                    flags = flagged(f"{row['headline'] or ''}\n{row['text'] or ''}")
                    if flags:
                        text = (row["text"] or "").replace("-\n", "")
                        spots = [m.start() for m in FLAGS.finditer(text)]
                        spots += [p for p in map(text.lower().find, flags) if p >= 0]
                        screened.append(
                            {
                                **for_reading(row, year, text, spots, most=6),
                                "flags": flags,
                                "first": None,
                                "rejudged": None,
                                "ghost_report": None,
                                "note": None,
                            }
                        )
                    continue
                if index not in (near if pool == "near_miss" else rand):
                    continue
                text = row["text"] or ""
                low = text.lower()
                spots = [m.start() for m in FLAGS.finditer(text)]
                spots += [
                    low.find(form.lower())
                    for forms in row["near_miss_terms"].values()
                    for form in forms
                ]
                recalled.append(
                    {
                        "pool": pool,
                        **for_reading(row, year, text, spots),
                        "ghost_report": None,
                        "note": None,
                    }
                )
    return year, docs, picked, recalled, no_batch_path, screened, tally


def quantiles(values, points=(0.1, 0.25, 0.5, 0.75, 0.9, 0.99)):
    ordered = sorted(values)
    return {
        f"p{round(q * 100)}": ordered[round(q * (len(ordered) - 1))] for q in points
    }


def keep_judgments(path, items, key, fields):
    """The freshly drawn items, with any judgment already made on them carried over."""
    if path.exists():
        made = {key(old): old for old in json.loads(path.read_text())}
        for item in items:
            for field in fields:
                item[field] = made.get(key(item), {}).get(field)
    path.write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n")
    return items


def rate(hits, n, of):
    low, high = wilson(hits, n)
    return {
        "count": hits,
        "n": n,
        "share": hits / n,
        "low": low,
        "high": high,
        "implied": round(hits / n * of),
        "implied_low": round(low * of),
        "implied_high": round(high * of),
    }


def main(data=DATA):
    counts = {
        c["year"]: c
        for c in (json.loads(p.read_text()) for p in (data / "counts").glob("*.json"))
    }
    years = sorted(counts)
    # one lexicon and one code version made the whole read
    (version,) = {counts[y]["lexicon_version"] for y in years}
    (code,) = {
        json.loads(p.read_text())["code_version"]
        for p in (data / "manifests").glob("*.json")
    }
    judged = version == "v1"
    name = "eval_a" if judged else f"eval_a_{version}"
    out = RESULTS / name
    # the read's ghost terms, in the lexicon's order
    read_terms = [
        term
        for term in (*lexicon.GHOST, *lexicon.TOGETHER)
        if any(term in counts[y]["by_term"] for y in years)
    ]
    total = {
        k: sum(counts[y][k] for y in years)
        for k in ("pages", "articles", "candidates", "near_miss")
    }
    others = {y: counts[y]["articles"] - counts[y]["candidates"] for y in years}
    total["non_candidates"] = sum(others.values())

    composition, near, rand, screen = (defaultdict(set) for _ in range(4))
    if judged:
        for year, index in uniform(
            {y: counts[y]["candidates"] for y in years},
            COMPOSITION,
            "eval A composition",
        ):
            composition[year].add(index)
        reservoirs = {y: range(min(SAMPLE_SIZE, counts[y]["near_miss"])) for y in years}
        for year, index in draw(
            reservoirs,
            {y: counts[y]["near_miss"] for y in years},
            RECALL,
            "eval A recall near-miss",
        ):
            near[year].add(index)
        rand, held, screen = random_picks(others)

    ghost = [term for term in read_terms if term in lexicon.GHOST]
    jobs = [
        (data, y, composition[y], near[y], rand[y], screen[y], ghost)
        for y in years
        if counts[y]["candidates"] or near[y] or rand[y] or screen[y]
    ]
    docs, years_of, picked, recalled, screened = [], [], [], [], []
    no_batch_path, tally = Counter(), Counter()
    with ProcessPoolExecutor(max_workers=6) as pool:
        for year, found, chosen, reread, missing, hits, drawn in pool.map(
            year_pass, sorted(jobs, key=lambda job: -counts[job[1]]["articles"])
        ):
            no_batch_path[year] = missing
            docs += found
            years_of += [year] * len(found)
            picked += chosen
            recalled += reread
            screened += hits
            tally.update(drawn)

    lengths = [doc[0] for doc in docs]
    qualities = [
        (year, doc[1])
        for year, doc in zip(years_of, docs, strict=True)
        if doc[1] is not None
    ]
    groups = clusters([doc[2] for doc in docs], least=2)
    group_sizes = sorted((len(g) for g in groups), reverse=True)
    cross = [g for g in groups if len({docs[d][3] for d in g}) > 1]
    rng = random.Random("eval A reprint check")
    checks = []
    for group in rng.sample(groups, min(REPRINT_CHECK, len(groups)) if judged else 0):
        a, b = rng.sample(group, 2)
        checks.append(
            {
                "size": len(group),
                "papers": len({docs[d][3] for d in group}),
                "years": [
                    min(years_of[d] for d in group),
                    max(years_of[d] for d in group),
                ],
                "members": [docs[a][4], docs[b][4]],
                "openings": [docs[a][5], docs[b][5]],
                "same_story": None,
            }
        )
    largest = [
        {
            "size": len(g),
            "papers": len({docs[d][3] for d in g}),
            "years": [min(years_of[d] for d in g), max(years_of[d] for d in g)],
            "example": docs[g[0]][5][:160],
        }
        for g in sorted(groups, key=len, reverse=True)[:10]
    ]

    printings = {docs[d][4]: len(g) for g in groups for d in g}
    for p in picked:
        p["printings"] = printings.get(p["article_id"], 1)

    out.mkdir(parents=True, exist_ok=True)
    if judged:
        picked = keep_judgments(
            out / "composition.json",
            sorted(picked, key=lambda p: (p["year"], p["article_id"])),
            lambda p: p["article_id"],
            ("category", "note"),
        )
        recalled = keep_judgments(
            out / "recall.json",
            sorted(recalled, key=lambda r: (r["pool"], r["year"], r["article_id"])),
            lambda r: (r["pool"], r["article_id"]),
            ("ghost_report", "note"),
        )
        screened = keep_judgments(
            out / "screen.json",
            sorted(screened, key=lambda s: (s["year"], s["article_id"])),
            lambda s: s["article_id"],
            ("first", "rejudged", "ghost_report", "note"),
        )
        checks = keep_judgments(
            out / "reprint-check.json",
            checks,
            lambda c: tuple(c["members"]),
            ("same_story",),
        )

    by_state = defaultdict(Counter)
    for year in years:
        for state, row in counts[year]["by_state"].items():
            by_state[state].update(row)
    terms = {
        term: sum(counts[y]["by_term"].get(term, 0) for y in years)
        for term in read_terms
    }
    only = {
        term: sum(counts[y]["only_by_term"].get(term, 0) for y in years)
        for term in read_terms
    }
    decade_quality = defaultdict(list)
    for year, quality in qualities:
        decade_quality[year // 10 * 10].append(quality)

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "lexicon_version": version,
        "code_version": code,
        "totals": {
            **total,
            "candidates_per_million": total["candidates"] / total["articles"] * 1e6,
            "no_batch_path": no_batch_path.total(),
            "share_no_batch_path": no_batch_path.total() / total["candidates"],
        },
        "by_year": [
            {
                "year": y,
                "pages": counts[y]["pages"],
                "articles": counts[y]["articles"],
                "candidates": counts[y]["candidates"],
                "near_miss": counts[y]["near_miss"],
                "no_batch_path": no_batch_path[y],
                "candidates_per_million": counts[y]["candidates"]
                / counts[y]["articles"]
                * 1e6
                if counts[y]["articles"]
                else 0,
            }
            for y in years
        ],
        "by_state": [
            {
                "state": state,
                **row,
                "candidates_per_million": row["candidates"] / row["articles"] * 1e6
                if row["articles"]
                else 0,
            }
            for state, row in sorted(
                by_state.items(), key=lambda kv: -kv[1]["candidates"]
            )
        ],
        "no_state": {
            "candidates": by_state["unknown"]["candidates"],
            "share_of_candidates": by_state["unknown"]["candidates"]
            / total["candidates"],
            "share_of_articles": by_state["unknown"]["articles"] / total["articles"],
        },
        "terms": {"any": terms, "only": only},
        "lengths": {
            "unit": "words of the article's text",
            "mean": sum(lengths) / len(lengths),
            **quantiles(lengths),
            "max": max(lengths),
            "histogram": length_histogram(lengths),
        },
        "ocr_quality": {
            "method": "share of words of 3+ letters in /usr/share/dict/words (Webster's 2nd), once line-break hyphens are joined and -s, -es, -ed, -ing, -ly, -ies, -ied come off",
            # so the figure can be checked against another machine's word list
            "dictionary": {
                "sha256": sha256(DICTIONARY),
                "words": len(DICTIONARY.read_text().splitlines()),
            },
            "sample": f"1 candidate in {OCR_ONE_IN}, by the CRC of its id: {len(qualities):,}",
            **quantiles([q for _, q in qualities]),
            "histogram": [
                sum(
                    1
                    for _, q in qualities
                    if lo <= q < lo + 0.05 or (lo == 0.95 and q == 1.0)
                )
                for lo in [i / 20 for i in range(20)]
            ],
            "median_by_decade": {
                d: quantiles(v, (0.5,))["p50"]
                for d, v in sorted(decade_quality.items())
            },
        },
        "reprints": {
            "method": "runs of 7 words of 3+ letters from each candidate's first 120, one in 8 kept by its hash; candidates sharing two of their six smallest runs, in a pair held by at most 1,000 candidates, are joined",
            "clusters": len(groups),
            "clustered_candidates": sum(group_sizes),
            "share_clustered": sum(group_sizes) / len(docs),
            "distinct_stories": len(docs) - sum(group_sizes) + len(groups),
            "cross_paper_clusters": len(cross),
            "cross_paper_candidates": sum(len(g) for g in cross),
            "size_histogram": size_histogram(group_sizes),
            "largest": largest,
        },
    }
    if judged:
        report["reprints"]["check"] = summarise_checks(checks)
        report["composition"] = summarise_composition(picked, total["candidates"])
        report["recall"] = summarise_recall(recalled, total)
        report["recall"]["screen"] = summarise_screen(
            screened,
            tally,
            recalled,
            picked,
            total,
            report["composition"].get("categories", {}).get("ghost_report"),
        )
        busiest = max(screen, key=lambda y: len(screen[y]))
        report["recall"]["screen"]["largest_year"] = {
            "year": busiest,
            "drawn": len(screen[busiest]),
            "held": len(held[busiest]),
        }
    (RESULTS / f"{name}.json").write_text(json.dumps(report, indent=1) + "\n")
    charts = draw_all(report, out)
    print(
        f"wrote {(RESULTS / f'{name}.json').relative_to(ROOT)} and {len(charts)} charts in {out.relative_to(ROOT)}"
    )
    for line in headline_numbers(report):
        print(line)


LENGTH_BINS = (0, 25, 50, 100, 200, 400, 800, 1600, 3200)
SIZE_BINS = ((2, 2), (3, 3), (4, 4), (5, 9), (10, 19), (20, 49), (50, 10**9))


def length_histogram(lengths):
    edges = list(LENGTH_BINS) + [10**9]
    return [
        {
            "from": lo,
            "to": hi - 1 if hi < 10**9 else None,
            "candidates": sum(1 for n in lengths if lo <= n < hi),
        }
        for lo, hi in itertools.pairwise(edges)
    ]


def size_histogram(sizes):
    return [
        {
            "from": lo,
            "to": hi if hi < 10**9 else None,
            "clusters": sum(1 for s in sizes if lo <= s <= hi),
            "candidates": sum(s for s in sizes if lo <= s <= hi),
        }
        for lo, hi in SIZE_BINS
    ]


def summarise_checks(checks):
    judged = [c for c in checks if c["same_story"] is not None]
    same = sum(bool(c["same_story"]) for c in judged)
    return {
        "judged": len(judged),
        "same_story": same,
        **(
            {"low": wilson(same, len(judged))[0], "high": wilson(same, len(judged))[1]}
            if judged
            else {}
        ),
    }


def summarise_composition(picked, candidates):
    judged = [p for p in picked if p["category"]]
    out = {
        "sample": len(picked),
        "judged": len(judged),
        "seed": "eval A composition",
        "stories": "each candidate counts as 1/k of a story when its reprint cluster holds k printings",
    }
    if judged:
        out["categories"] = {
            c: rate(sum(p["category"] == c for p in judged), len(judged), candidates)
            | {
                "stories": round(
                    sum(1 / p["printings"] for p in judged if p["category"] == c)
                    / len(judged)
                    * candidates
                )
            }
            for c in CATEGORIES
        }
    return out


def summarise_recall(recalled, total):
    out = {}
    for pool, size, seed in (
        ("near_miss", total["near_miss"], "eval A recall near-miss"),
        ("random", total["non_candidates"], "eval A recall random"),
    ):
        items = [r for r in recalled if r["pool"] == pool]
        judged = [r for r in items if r["ghost_report"] is not None]
        found = [r for r in judged if r["ghost_report"]]
        out[pool] = {
            "sample": len(items),
            "judged": len(judged),
            "seed": seed,
            "pool_size": size,
        }
        if judged:
            out[pool].update(rate(len(found), len(judged), size))
            out[pool]["reports"] = [
                {
                    k: r[k]
                    for k in ("article_id", "year", "date", "paper", "headline", "note")
                }
                for r in found
            ]
    return out


def summarise_screen(screened, tally, recalled, picked, total, in_candidates):
    """Decision 30. The bound on reports among non-candidates, from the screen's draw and the
    300 random articles read in full, and among the near-miss pool, from the draw's near-miss
    articles and the 300 near-miss ones. Both hold once every screen hit is judged."""
    judged = [s for s in screened if s["ghost_report"] is not None]
    checked = [s for s in judged if s["first"] == "no" and s["rejudged"]]
    reports = [p for p in picked if p["category"] == "ghost_report"]
    out = {
        "seed": "eval A screen",
        "drawn": tally["drawn"],
        "drawn_near_miss": tally["near_miss"],
        "hits": len(screened),
        "judged": len(judged),
        "first_reading": dict(Counter(s["first"] for s in judged)),
        "negatives_rejudged": len(checked),
        "negatives_agreed": sum(not s["ghost_report"] for s in checked),
        "reports_flagged_without_terms": {
            "count": sum(bool(p["flags_without_terms"]) for p in reports),
            "of": len(reports),
            "flags": {p["article_id"]: p["flags_without_terms"] for p in reports},
        },
    }
    if not screened or len(judged) < len(screened):
        return out
    read = [r for r in recalled if r["pool"] == "random"]
    found = [s for s in judged if s["ghost_report"]] + [
        r for r in read if r["ghost_report"]
    ]
    out["random"] = rate(
        len(found), tally["drawn"] + len(read), total["non_candidates"]
    )
    out["reports"] = [
        {k: r[k] for k in ("article_id", "year", "date", "paper", "headline", "note")}
        for r in found
    ]
    near = {r["article_id"]: r for r in recalled if r["pool"] == "near_miss"}
    near |= {s["article_id"]: s for s in screened if s["near_miss_terms"]}
    out["near_miss"] = rate(
        sum(bool(r["ghost_report"]) for r in near.values()),
        len(near),
        total["near_miss"],
    )
    if in_candidates:
        # the reports among candidates, at composition's low, point and high, over those plus
        # the most that non-candidates can hold
        missed = out["random"]["implied_high"]
        out["recall"] = in_candidates["implied"] / (
            in_candidates["implied"] + out["random"]["implied"]
        )
        out["recall_at_least"] = {
            name: in_candidates[at] / (in_candidates[at] + missed)
            for name, at in (
                ("low", "implied_low"),
                ("point", "implied"),
                ("high", "implied_high"),
            )
        }
    return out


def headline_numbers(report):
    t = report["totals"]
    r = report["reprints"]
    yield f"{t['articles']:,} articles in {t['pages']:,} pages; {t['candidates']:,} candidates ({t['candidates_per_million']:.0f} per million), {t['near_miss']:,} near-miss"
    yield f"no state: {report['no_state']['share_of_candidates']:.1%} of candidates; median length {report['lengths']['p50']} words; median OCR quality {report['ocr_quality']['p50']:.1%}"
    yield f"no batch path: {t['no_batch_path']:,} candidates ({t['share_no_batch_path']:.1%}), which need loc.gov to name their page's IIIF service"
    yield f"reprints: {r['clusters']:,} clusters hold {r['clustered_candidates']:,} candidates ({r['share_clustered']:.1%}); {r['distinct_stories']:,} distinct stories; {r['cross_paper_clusters']:,} clusters span papers"
    s = report.get("recall", {}).get("screen")
    if not s:
        return
    yield f"screen: {s['hits']:,} of {s['drawn']:,} drawn hold a flag word, {s['judged']:,} judged"
    if "random" in s:
        yield f"  non-candidates: {s['random']['count']} reports in {s['random']['n']:,}, at most {s['random']['implied_high']:,}; recall {s['recall']:.1%}, at least {s['recall_at_least']['point']:.1%}"
        yield f"  near-miss: {s['near_miss']['count']} in {s['near_miss']['n']:,}, at most {s['near_miss']['implied_high']:,}"


if __name__ == "__main__":
    main(Path(sys.argv[1]) if sys.argv[1:] else DATA)
