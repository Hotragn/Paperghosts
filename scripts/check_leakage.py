"""RDR-4: training data is disjoint from gold and dev, reprints of their stories included
(decision 37). Gold and dev are drawn from every candidate and the near-miss reservoir. The
training pool is what's left of both outside the groups of gold, dev and the quarantine. The
random reservoir stays out of training, since eval B screens it for recall.

  check     the default: exits 0 only if eval/gold/split.json holds. That means no group of the
            inclusive grouping spans gold and dev, or a held article and the pool. No pool
            article shares at least FEWEST of its whole text's five-word runs, and LEAK of the
            shorter's, with a gold or dev article, and gold shares none so with dev. No gold or
            dev article is a POLICY.md example, in an example's group or a reprint of one, and
            each file HASH lists, the split and from 2C.2 the frozen labels, matches it.
            Written to eval/results/phase2c/leakage.json.
  justify   the threshold, on decision 36's labelled pairs, in
            eval/results/phase2c/leakage_threshold.json
"""

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

import numpy as np
import zstandard
from clusters import SETS, features

from paperghosts.cluster.reprints import groups, keys, shingles

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "gold"
SPLIT = GOLD / "split.json"
HASH = GOLD / "HASH"
ARCHIVE = Path(
    "data", "archive", "lexicon-v1", "samples"
)  # lexicon v1's samples (decision 31)
RESULTS = ROOT / "eval" / "results" / "phase2c"
# a pool article reprints a held one when they share at least FEWEST whole-text runs, and those
# are at least LEAK of the shorter's. Every one-story pair of decision 36's randomly drawn strata
# passes: the lowest share is 0.105 and the fewest runs 6 (justify, leakage_threshold.json)
LEAK, FEWEST = 0.10, 5
# a POLICY.md example's article id
EXAMPLE = re.compile(r"\d+_\d{4}-\d\d-\d\d_[A-Za-z0-9_]+?\.json")


def runs(text) -> np.ndarray:
    """Every five-word run of the whole text, none sampled."""
    return shingles(text, window=None, sample=1)


def flagged(shared: int, a: int, b: int) -> bool:
    """Whether two texts with a and b runs, sharing `shared`, are taken for one story."""
    return shared >= FEWEST and shared >= LEAK * min(a, b)


def near_misses(path: Path) -> list:
    """One year's near-miss reservoir: id, date, and its opening's and body's runs."""
    with zstandard.open(path, "rt") as rows:
        return [
            (
                row["article_id"],
                row["date"],
                tuple(keys(row["text"])),
                tuple(keys(row["text"], start=120)),
            )
            for row in map(json.loads, rows)
            if row["sample"] == "near_miss"
        ]


def frame(root: Path = ROOT) -> dict:
    """Every article gold and dev are drawn from, candidates first and then the near-miss
    reservoir, with its id, its date and its group in the inclusive grouping. A group is named
    by its earliest member, and an article in none is a group of its own."""
    found = features(root)
    paths = sorted((root / "data" / "samples").glob("*.jsonl.zst"))
    with ProcessPoolExecutor(max_workers=8) as pool:
        extra = [row for year in pool.map(near_misses, paths) for row in year]
    ids = found["ids"] + [r[0] for r in extra]
    dates = found["dates"] + [r[1] for r in extra]
    linked = groups(
        found["keys"] + [r[2] for r in extra], found["body"] + [r[3] for r in extra]
    )
    group = list(ids)
    for members in linked:
        first = ids[min(members, key=lambda d: (dates[d], ids[d]))]
        for doc in members:
            group[doc] = first
    return {"ids": ids, "dates": dates, "group": group, "candidates": len(found["ids"])}


def hashes_hold(listed: Path = HASH) -> bool:
    """Whether each file HASH lists by name, split.json among them, has the sha256 it lists."""
    found = {
        name: sha
        for sha, name in (
            line.split() for line in listed.read_text().splitlines() if line.strip()
        )
    }
    return "split.json" in found and all(
        hashlib.sha256((listed.parent / name).read_bytes()).hexdigest() == sha
        for name, sha in found.items()
    )


def examples(root: Path = ROOT) -> set:
    """The articles POLICY.md names as its rules' examples."""
    return set(EXAMPLE.findall((root / "eval" / "gold" / "POLICY.md").read_text()))


def paths_of(root: Path) -> list:
    return sorted((root / "data" / "candidates").glob("*.jsonl.zst")) + sorted(
        (root / "data" / "samples").glob("*.jsonl.zst")
    )


def texts_in(path: Path, wanted: set) -> dict:
    with zstandard.open(path, "rt") as rows:
        return {
            row["article_id"]: row["text"] or ""
            for row in map(json.loads, rows)
            if row["article_id"] in wanted
        }


def whole_texts(root: Path, wanted: set, paths: list | None = None) -> dict:
    """The whole text of each wanted article, from the candidates or the samples."""
    with ProcessPoolExecutor(max_workers=8) as pool:
        parts = pool.map(partial(texts_in, wanted=wanted), paths or paths_of(root))
        return {aid: text for part in parts for aid, text in part.items()}


HELD = {}  # each worker's copy of the held runs, set once by the pool's initializer


def hold(held: dict) -> None:
    HELD.update(held)


def leaks_in(path: Path) -> list:
    """The pool articles in one file, outside the excluded ones, that reprint a held article:
    (pool article, held article, runs shared, share of the shorter's)."""
    every, owners, sizes = HELD["every"], HELD["owners"], HELD["sizes"]
    found = []
    with zstandard.open(path, "rt") as rows:
        for row in map(json.loads, rows):
            if row.get("sample") == "random" or row["article_id"] in HELD["excluded"]:
                continue
            mine = runs(row["text"])
            # every is sorted, so a binary search finds the shared runs without re-sorting it
            at = np.minimum(np.searchsorted(every, mine), len(every) - 1)
            common = mine[every[at] == mine]
            if len(common) < FEWEST:
                continue
            shared = Counter(held for run in common.tolist() for held in owners[run])
            for held, n in shared.items():
                if flagged(n, len(mine), sizes[held]):
                    share = round(n / min(len(mine), sizes[held]), 4)
                    found.append((row["article_id"], held, n, share))
    return found


def leaks(root: Path, held: dict, excluded: set, workers: int = 8) -> list:
    """Every article of the candidates and the near-miss reservoir, outside `excluded`, that
    reprints one of the held texts (article id to text)."""
    held_runs = {aid: runs(text) for aid, text in held.items()}
    if not any(len(mine) for mine in held_runs.values()):
        return []
    owners = defaultdict(list)
    for aid, mine in held_runs.items():
        for run in mine.tolist():
            owners[run].append(aid)
    shared = {
        "every": np.array(sorted(owners), dtype=np.uint64),
        "owners": dict(owners),
        "sizes": {aid: len(mine) for aid, mine in held_runs.items()},
        "excluded": excluded,
    }
    with ProcessPoolExecutor(workers, initializer=hold, initargs=(shared,)) as pool:
        return [leak for year in pool.map(leaks_in, paths_of(root)) for leak in year]


def between(a: dict, b: dict) -> list:
    """The pairs of an article of a and one of b (each article id to text) that are taken for
    one story."""
    a_runs = {aid: runs(text) for aid, text in a.items()}
    b_runs = {aid: runs(text) for aid, text in b.items()}
    return sorted(
        (x, y)
        for x, mine in a_runs.items()
        for y, theirs in b_runs.items()
        if flagged(
            len(np.intersect1d(mine, theirs, assume_unique=True)),
            len(mine),
            len(theirs),
        )
    )


def crossings(found: dict, gold: set, dev: set, held: set, out: set) -> list:
    """The groups that cross the split: one that holds gold and dev, or a held article (gold,
    dev or quarantined) and an article still in the pool."""
    sides = defaultdict(set)
    for aid, group in zip(found["ids"], found["group"], strict=True):
        sides[group].add(
            "gold"
            if aid in gold
            else "dev"
            if aid in dev
            else "held"
            if aid in held
            else "out"
            if aid in out
            else "pool"
        )
    return sorted(
        group
        for group, side in sides.items()
        if {"gold", "dev"} <= side
        or (side & {"gold", "dev", "held"} and "pool" in side)
    )


def check(root: Path = ROOT) -> dict:
    split = json.loads(SPLIT.read_text())
    gold = {item["article_id"] for item in split["gold"]}
    dev = {item["article_id"] for item in split["dev"]}
    held = gold | dev | {item["article_id"] for item in split["quarantine"]}
    out = set(split["out_of_pool"])
    found = frame(root)
    group_of = dict(zip(found["ids"], found["group"], strict=True))
    named = examples(root)
    example_groups = {group_of[aid] for aid in named if aid in group_of}
    texts = whole_texts(root, gold | dev)
    shown = whole_texts(root, named)
    # three examples are lexicon v1's random samples from eval A's screen, in no file drawn from
    shown |= whole_texts(
        root, named - shown.keys(), sorted((root / ARCHIVE).glob("*.jsonl.zst"))
    )
    hashed = hashes_hold()
    result = {
        "gold": len(gold),
        "dev": len(dev),
        "out_of_pool": len(out),
        "pool": len(found["ids"]) - len(out),
        "gold_between_150_and_300": 150 <= len(gold) <= 300,
        "not_in_the_frame": sorted((gold | dev) - set(group_of)),
        "crossing_groups": crossings(found, gold, dev, held, out),
        "pool_reprints": leaks(root, texts, out),
        "gold_reprinting_dev": between(
            {aid: texts[aid] for aid in gold}, {aid: texts[aid] for aid in dev}
        ),
        "examples_drawn": sorted(
            aid
            for aid in gold | dev
            if aid in named or group_of.get(aid) in example_groups
        ),
        "examples_unread": sorted(named - shown.keys()),
        "examples_reprinted": between(shown, texts),
        "hash_matches": hashed,
        "rule": {"leak": LEAK, "fewest": FEWEST},
    }
    result["passed"] = (
        result["gold_between_150_and_300"]
        and hashed
        and not any(
            result[k]
            for k in (
                "not_in_the_frame",
                "crossing_groups",
                "pool_reprints",
                "gold_reprinting_dev",
                "examples_drawn",
                "examples_unread",
                "examples_reprinted",
            )
        )
    )
    return result


def justify(root: Path = ROOT) -> dict:
    """The rule on decision 36's labelled pairs, stratum by stratum: how many of the one-story
    pairs it flags, and how many of the pairs of two stories. The randomly drawn strata stand
    for the reprints a whole-text check must catch. The large clusters' least similar pairs
    are left out of that count, since eval A's links already group them."""
    labelled = [
        dict(pair, set=name)
        for name in ("eval", "dev")
        for pair in json.loads((SETS / f"{name}.json").read_text())
    ]
    texts = whole_texts(root, {pair[side] for pair in labelled for side in "ab"})
    strata = defaultdict(lambda: {"same": [0, 0], "different": [0, 0]})
    drawn = []
    for pair in labelled:
        a, b = runs(texts[pair["a"]]), runs(texts[pair["b"]])
        shared = len(np.intersect1d(a, b, assume_unique=True))
        hit = flagged(shared, len(a), len(b))
        cell = strata[f"{pair['set']}, {pair['stratum']}"][pair["label"]]
        cell[0] += hit
        cell[1] += 1
        if pair["label"] == "same" and not pair["stratum"].startswith("large"):
            share = shared / min(len(a), len(b)) if len(a) and len(b) else 0.0
            drawn.append((round(share, 4), shared, pair["pair"], hit))
    return {
        "rule": {"leak": LEAK, "fewest": FEWEST},
        "flagged_of": {
            name: {label: f"{k} of {n}" for label, (k, n) in cell.items()}
            for name, cell in sorted(strata.items())
        },
        "one_story_drawn_at_random": {
            "pairs": len(drawn),
            "flagged": sum(hit for *_, hit in drawn),
            "lowest_shares": sorted(drawn)[:5],
            "fewest_runs": sorted(drawn, key=lambda d: d[1])[:5],
        },
    }


def main(run: str = "check", root: Path = ROOT) -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    if run == "justify":
        out = justify(root)
        (RESULTS / "leakage_threshold.json").write_text(
            json.dumps(out, indent=1) + "\n"
        )
        print(json.dumps(out, indent=1))
        return 0
    out = check(root)
    (RESULTS / "leakage.json").write_text(json.dumps(out, indent=1) + "\n")
    print(
        json.dumps({k: v for k, v in out.items() if not isinstance(v, list)}, indent=1)
    )
    print({k: len(v) for k, v in out.items() if isinstance(v, list)})
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
