"""The gold set's draw and the split (decision 37), seeded, after POLICY.md and before any label.

Every candidate falls in one stratum, the first of these that fits:
1. three edge-case slices the archive holds too few of to meet by chance (SRS 7.3): phantom
   ships, trains and lights (E8), hoaxes and pranksters (E6), and text not in English (E12)
2. printed before 1850, so the early decades are read
3. otherwise the rarest of lexicon v2's five rules it holds, or none, split by whether a ghost
   term is in the headline. A term in the headline is where reports gather: 7 of 27 judged
   against 14 of 373.

A near-miss stratum comes from the near-miss reservoir, each year in proportion to its pool,
so triage can be measured on gold. Within a candidate stratum the draw is systematic in date
order, so each decade gets its share. Each article's inclusion probability is its stratum's
draw over its size. Dev is drawn the same way at half the size, from outside gold's groups.
POLICY.md's examples and their groups are left out of both.

The training pool is every other article of the candidates and the near-miss reservoir,
outside the groups of gold and dev, and outside the quarantine: the pool articles the
whole-text check finds reprinting a gold or dev article, with their groups. Writes
eval/gold/split.json, its sha256 in eval/gold/HASH, and the design's numbers in
eval/results/phase2c/gold_draw.json.
"""

import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import zstandard
from check_leakage import (
    FEWEST,
    HASH,
    LEAK,
    RESULTS,
    SPLIT,
    between,
    examples,
    frame,
    leaks,
    whole_texts,
)
from eval_a import draw

from paperghosts.ingest.lexicon import ghost_terms
from paperghosts.stats import wilson

ROOT = Path(__file__).resolve().parents[1]
SEED = "2C.1 gold"
RULES = (
    "ouija",
    "seance",
    "spirit_phrase",
    "spiritualism",
    "spirit+medium",
)  # rarest first
SHIPS = re.compile(
    r"\b(?:phantom|ghost|spectre|specter|spectral)[\s-]+"
    r"(?:ship|vessel|schooner|steamer|bark|brig|train|engine|light|lantern)s?\b",
    re.IGNORECASE,
)
HOAX = re.compile(r"\bhoax|\bpractical jok|\bprankster", re.IGNORECASE)
# common short words of German, French, Spanish, Dutch and the Scandinavian languages
FOREIGN = re.compile(
    r"\b(?:und|der|die|das|nicht|ein|ist|les|est|une|dans|pour|los|las|del|por|que"
    r"|het|een|og|och)\b"
)
ENGLISH = re.compile(r"\b(?:the|and|of|to|was|that)\b")
NEAR = "near misses"
# (gold, dev) for each stratum, in the order a candidate is placed
ALLOCATION = {
    "E8: phantom ships, trains and lights": (8, 4),
    "E6: hoaxes and pranksters": (8, 4),
    "E12: not in English": (7, 3),
    "before 1850": (20, 10),
    "ouija, term in the headline": (8, 4),
    "ouija, none in the headline": (12, 6),
    "seance, term in the headline": (10, 5),
    "seance, none in the headline": (12, 6),
    "spirit_phrase, term in the headline": (10, 5),
    "spirit_phrase, none in the headline": (12, 6),
    "spiritualism, term in the headline": (10, 5),
    "spiritualism, none in the headline": (12, 6),
    "spirit+medium, term in the headline": (6, 3),
    "spirit+medium, none in the headline": (14, 7),
    "v1 terms only, term in the headline": (80, 40),
    "v1 terms only, none in the headline": (46, 23),
    NEAR: (25, 13),
}
JUDGED = ROOT / "eval" / "results"


def stratum(row: dict) -> str:
    text = row["text"] or ""
    if SHIPS.search(text):
        return "E8: phantom ships, trains and lights"
    if HOAX.search(text):
        return "E6: hoaxes and pranksters"
    low = text.lower()
    foreign = len(FOREIGN.findall(low))
    if foreign >= 8 and foreign > 2 * len(ENGLISH.findall(low)):
        return "E12: not in English"
    if row["date"] < "1850":
        return "before 1850"
    rule = next((t for t in RULES if t in row["terms"]), "v1 terms only")
    return f"{rule}, {'term' if ghost_terms(row['headline'] or '') else 'none'} in the headline"


def strata_in(path: Path) -> list:
    with zstandard.open(path, "rt") as rows:
        return [(row["article_id"], stratum(row)) for row in map(json.loads, rows)]


def systematic(units: list, n: int, rng: random.Random) -> list:
    """n of the units, which are in date order: one every len(units) / n from a seeded start.
    Each is drawn with probability n / len(units), and each decade gets its share of the n,
    give or take one."""
    step = len(units) / n
    start = rng.random() * step
    return [units[min(int(start + i * step), len(units) - 1)] for i in range(n)]


def take(units: dict, near: dict, sizes: dict, banned: set, which: int, seed: str):
    """Each stratum's draw, for gold (which=0) or dev (which=1), from the articles outside
    `banned`, with the number of articles it was drawn from."""
    rng = random.Random(seed)
    out = {}
    for name, counts in ALLOCATION.items():
        if name == NEAR:
            pools = {y: [a for a in ids if a not in banned] for y, ids in near.items()}
            picks = draw(pools, sizes, counts[which], f"{seed} near misses")
            size = sum(sizes[y] for y, ids in pools.items() if ids and sizes.get(y))
            out[name] = ([aid for _, aid in picks], size)
        else:
            eligible = sorted(u for u in units[name] if u[1] not in banned)
            out[name] = (
                [aid for _, aid in systematic(eligible, counts[which], rng)],
                len(eligible),
            )
    return out


def items(drawn: dict, found: dict, index: dict) -> list:
    return [
        {
            "article_id": aid,
            "stratum": name,
            "date": found["dates"][index[aid]],
            "group": found["group"][index[aid]],
            "pi": len(ids) / size,
            "weight": size / len(ids),
        }
        for name, (ids, size) in drawn.items()
        for aid in ids
    ]


def members(found: dict, of: set) -> set:
    """Every article in the groups of these articles."""
    index = {aid: i for i, aid in enumerate(found["ids"])}
    wanted = {found["group"][index[aid]] for aid in of if aid in index}
    return {
        aid
        for aid, group in zip(found["ids"], found["group"], strict=True)
        if group in wanted
    }


def decades(drawn: dict, found: dict, index: dict) -> dict:
    dates = (found["dates"][index[aid]] for ids, _ in drawn.values() for aid in ids)
    return dict(sorted(Counter(date[:3] + "0s" for date in dates).items()))


def rate_class(name: str) -> str:
    """Where a stratum's report rate is read from: the five rules' strata pool their judged
    items, which are too few apart."""
    rule, _, headline = name.partition(", ")
    return f"a v2 rule, {headline}" if rule in RULES else name


def judged_rates(placed: dict) -> dict:
    """The report rate of each rate class, on what eval A and lexicon v2 judged (decisions 27,
    30 and 31): eval A's 200 candidates, lexicon v2's 200 added ones, and eval A's 300 from
    the near-miss reservoirs."""
    seen = [
        (x["article_id"], x["category"] == "ghost_report")
        for x in json.loads((JUDGED / "eval_a" / "composition.json").read_text())
    ] + [
        (x["article_id"], x["ghost_report"])
        for x in json.loads((JUDGED / "eval_a_v2" / "added.json").read_text())
    ]
    tally = defaultdict(lambda: [0, 0])
    for aid, report in seen:
        cell = tally[rate_class(placed[aid])]
        cell[0] += report
        cell[1] += 1
    for x in json.loads((JUDGED / "eval_a" / "recall.json").read_text()):
        if x["pool"] == "near_miss":
            tally[NEAR][0] += x["ghost_report"]
            tally[NEAR][1] += 1
    return dict(tally)


def expected(rates: dict, sizes: dict) -> dict:
    """Gold's expected reports, stratum by stratum, at the judged rates, with each Wilson
    interval's ends. The total's range adds those ends, so it is wider than its own interval."""
    rows, total = {}, [0.0, 0.0, 0.0]
    for name, (n, _) in ALLOCATION.items():
        hits, judged = rates.get(rate_class(name), (0, 0))
        if not judged:
            rows[name] = {"gold": n, "judged": "none", "reports": None}
            continue
        low, high = wilson(hits, judged)
        row = [n * hits / judged, n * low, n * high]
        total = [t + r for t, r in zip(total, row, strict=True)]
        rows[name] = {
            "gold": n,
            "drawn_from": sizes[name],
            "judged": f"{hits} of {judged}",
            "reports": [round(r, 1) for r in row],
        }
    return {"strata": rows, "total": [round(t, 1) for t in total]}


def main(root: Path = ROOT) -> None:
    found = frame(root)
    index = {aid: i for i, aid in enumerate(found["ids"])}
    paths = sorted((root / "data" / "candidates").glob("*.jsonl.zst"))
    with ProcessPoolExecutor(max_workers=8) as pool:
        placed = dict(pair for year in pool.map(strata_in, paths) for pair in year)
    units = defaultdict(list)
    for aid, name in placed.items():
        units[name].append((found["dates"][index[aid]], aid))
    near = defaultdict(list)
    for aid in found["ids"][found["candidates"] :]:
        near[found["dates"][index[aid]][:4]].append(aid)
    sizes = {
        p.stem: json.loads(p.read_text())["near_miss"]
        for p in sorted((root / "data" / "counts").glob("*.json"))
    }

    named = examples(root)
    banned = named | members(found, named)
    gold = take(units, near, sizes, banned, 0, SEED)
    gold_ids = {aid for ids, _ in gold.values() for aid in ids}
    texts = whole_texts(root, gold_ids)
    dev_banned = banned | members(found, gold_ids)
    while (
        True
    ):  # a dev article reprinting a gold one is left out with its group, and redrawn
        dev = take(units, near, sizes, dev_banned, 1, f"{SEED} dev")
        dev_ids = {aid for ids, _ in dev.values() for aid in ids}
        texts |= whole_texts(root, dev_ids - texts.keys())
        clash = between({a: texts[a] for a in gold_ids}, {a: texts[a] for a in dev_ids})
        if not clash:
            break
        dev_banned |= members(found, {d for _, d in clash})
        print("redrawing dev without", clash)

    out = members(found, gold_ids | dev_ids)
    flagged = leaks(root, {a: texts[a] for a in gold_ids | dev_ids}, out)
    quarantine = sorted({pool for pool, *_ in flagged})
    out |= set(quarantine) | members(found, set(quarantine))

    split = {
        "decision": 37,
        "seed": SEED,
        "policy_sha256": hashlib.sha256(
            (root / "eval" / "gold" / "POLICY.md").read_bytes()
        ).hexdigest(),
        "rule": {"leak": LEAK, "fewest": FEWEST},
        "strata": [
            {
                "stratum": name,
                "gold": len(gold[name][0]),
                "gold_drawn_from": gold[name][1],
                "dev": len(dev[name][0]),
                "dev_drawn_from": dev[name][1],
            }
            for name in ALLOCATION
        ],
        "gold": items(gold, found, index),
        "dev": items(dev, found, index),
        "quarantine": [
            {"article_id": pool, "reprints": held, "shared": n, "share": share}
            for pool, held, n, share in sorted(flagged)
        ],
        "out_of_pool": sorted(out),
        "pool": (
            "Every other article of the candidates and the near-miss reservoir. 2C.4 draws at "
            "most one printing per story from it."
        ),
    }
    SPLIT.write_text(json.dumps(split, indent=1) + "\n")
    HASH.write_text(f"{hashlib.sha256(SPLIT.read_bytes()).hexdigest()}  split.json\n")

    rates = judged_rates(placed)
    sizes_of = Counter(found["group"])
    report = {
        "population": dict(sorted(Counter(placed.values()).items())),
        "judged_rates": {k: f"{h} of {n}" for k, (h, n) in sorted(rates.items())},
        "expected_reports": expected(rates, {k: v[1] for k, v in gold.items()}),
        "decades": {
            "gold": decades(gold, found, index),
            "dev": decades(dev, found, index),
        },
        "grouping": {
            "articles": len(found["ids"]),
            "groups_of_two_or_more": sum(1 for s in sizes_of.values() if s > 1),
            "articles_in_them": sum(s for s in sizes_of.values() if s > 1),
            "largest": max(sizes_of.values()),
        },
        "split": {
            "gold": len(gold_ids),
            "dev": len(dev_ids),
            "left_out_for_policy_examples": len(banned),
            "quarantine": len(quarantine),
            "out_of_pool": len(out),
            "pool": len(found["ids"]) - len(out),
        },
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "gold_draw.json").write_text(json.dumps(report, indent=1) + "\n")
    print(
        json.dumps({k: report[k] for k in ("split", "grouping", "decades")}, indent=1)
    )
    print("expected reports", report["expected_reports"]["total"])


if __name__ == "__main__":
    main()
