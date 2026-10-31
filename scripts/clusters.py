"""Reprint clusters as stories (decision 36). Eval A's links stay, two shared runs among each
candidate's six smallest in its opening, but a printing joins a story only by matching the
story's first printing directly, so no chain of links joins stories that share nothing.

  build     every candidate's runs and shingles, cached in data/clusters/features.pkl; eval A's
            clusters, which are the frame; and the stories at THRESHOLD, reported in
            eval/results/phase2b/clusters.json
  draw      the evaluation set and the dev set, seeded, from the frame and the body probe, in
            eval/clusters/eval.json and dev.json, and the reading agents' batches of texts in
            data/clusters/batches/, which name no stratum and no score
  freeze    the labelled evaluation set's sha256, in eval/clusters/frozen.json
  tune      the stories at each threshold of GRID, scored on the labelled dev set
  score     precision and recall of same-story links on the frozen evaluation set
"""

import hashlib
import json
import pickle
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from itertools import pairwise
from pathlib import Path

import numpy as np
import zstandard

from paperghosts.cluster.reprints import (
    BOILERPLATE,
    WORD,
    clusters,
    keys,
    overlap,
    pairs,
    shingles,
    stories,
)
from paperghosts.stats import wilson

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "clusters"
FEATURES = DATA / "features.pkl"
BATCHES = DATA / "batches"
SETS = ROOT / "eval" / "clusters"
REPORT = ROOT / "eval" / "results" / "phase2b" / "clusters.json"
THRESHOLD = 0.5  # provisional, set before any labels: tune replaces it from the dev set
LOOSE = 1.25  # a member this much longer than its story's first printing is read too
GRID = [round(0.2 + 0.05 * i, 2) for i in range(13)]  # 0.2 to 0.8
LARGE = 50  # printings in a cluster that gets its least similar pair checked by hand
WORDS_SHOWN = 400  # of each printing, for the reading agents
EMPTY = np.array([], dtype=np.uint64)


def read_year(path: Path) -> list:
    """One year's candidates: id, date, LCCN, length in words of 3+ letters, the opening's
    runs, the body's runs (from word 120), and the shingles."""
    found = []
    with zstandard.open(path, "rt") as rows:
        for row in map(json.loads, rows):
            text = row["text"] or ""
            found.append(
                (
                    row["article_id"],
                    row["date"],
                    row["lccn"],
                    len(WORD.findall(text.lower())),
                    tuple(sorted(keys(text))),
                    tuple(sorted(keys(text, start=120))),
                    shingles(text),
                )
            )
    return found


def features(root: Path = ROOT) -> dict:
    """Every candidate's id, date, LCCN, runs and body runs; the shingles of those eval A
    clusters; and eval A's clusters themselves. Cached, since reading takes minutes."""
    if FEATURES.exists():
        return pickle.loads(FEATURES.read_bytes())
    paths = sorted((root / "data" / "candidates").glob("*.jsonl.zst"))
    with ProcessPoolExecutor(max_workers=8) as pool:
        rows = [row for year in pool.map(read_year, paths) for row in year]
    groups = clusters([set(r[4]) for r in rows], least=2)
    clustered = {d for g in groups for d in g}
    found = {
        "ids": [r[0] for r in rows],
        "dates": [r[1] for r in rows],
        "lccns": [r[2] for r in rows],
        "words": [r[3] for r in rows],
        "keys": [r[4] for r in rows],
        "body": [r[5] for r in rows],
        "shingles": {d: rows[d][6] for d in clustered},
        "frame": groups,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    FEATURES.write_bytes(pickle.dumps(found, protocol=5))
    return found


def order_of(found: dict) -> list:
    """Every candidate, earliest first; a story's first printing names it."""
    return sorted(
        range(len(found["ids"])), key=lambda d: (found["dates"][d], found["ids"][d])
    )


def stories_at(found: dict, threshold: float) -> tuple:
    texts = [found["shingles"].get(d, EMPTY) for d in range(len(found["ids"]))]
    return stories(
        [set(k) for k in found["keys"]], texts, order_of(found), threshold, BOILERPLATE
    )


def similarity(found: dict, a: int, b: int) -> list:
    shared, of_shorter, of_longer = overlap(found["shingles"][a], found["shingles"][b])
    return [shared, round(of_shorter, 4), round(of_longer, 4)]


def least_similar(found: dict, group: list) -> tuple:
    """The pair of a cluster's printings that share the least of the shorter's shingles."""
    worst, pair = 2.0, (group[0], group[1])
    for i, a in enumerate(group):
        for b in group[i + 1 :]:
            score = overlap(found["shingles"][a], found["shingles"][b])[1]
            if score < worst:
                worst, pair = score, (a, b)
    return pair


def report(found: dict, story: list, match: list, threshold: float) -> dict:
    """What the stories at threshold make of the candidates, beside eval A's clusters."""
    members = defaultdict(list)
    for doc, first in enumerate(story):
        members[first].append(doc)
    shared = [m for m in members.values() if len(m) > 1]
    sizes = Counter(len(m) for m in shared)
    loose = sum(
        1
        for doc, first in enumerate(story)
        if first != doc and found["words"][doc] >= LOOSE * found["words"][first]
    )
    frame = found["frame"]
    large = []
    for group in sorted(frame, key=len, reverse=True):
        if len(group) < LARGE:
            break
        parts = Counter(story[d] for d in group)
        large.append(
            {
                "printings": len(group),
                "papers": len({found["lccns"][d] for d in group}),
                "stories": len(parts),
                "largest_story": max(parts.values()),
                "first": found["ids"][min(group, key=order_of_key(found))],
            }
        )
    bands = [(2, 2), (3, 3), (4, 4), (5, 9), (10, 19), (20, 49), (50, None)]
    return {
        "threshold": threshold,
        "loose": LOOSE,
        "candidates": len(story),
        "frame": {
            "clusters": len(frame),
            "clustered_candidates": sum(map(len, frame)),
            "distinct_stories": len(story) - sum(map(len, frame)) + len(frame),
        },
        "stories": {
            "with_more_than_one_printing": len(shared),
            "printings_in_them": sum(map(len, shared)),
            "share_of_candidates": round(sum(map(len, shared)) / len(story), 4),
            "distinct_stories": len(members),
            "cross_paper": sum(len({found["lccns"][d] for d in m}) > 1 for m in shared),
            "first_printings_that_match_their_members_directly": "every one, by construction",
            "size_histogram": [
                {
                    "from": low,
                    "to": high,
                    "stories": sum(
                        n
                        for size, n in sizes.items()
                        if size >= low and (high is None or size <= high)
                    ),
                }
                for low, high in bands
            ],
            "lowest_match_kept": round(min(m for m in match), 4),
        },
        "reader": {
            "reads": "each story's first printing, and every member at least "
            f"{LOOSE - 1:.0%} longer than it, whose extra text might hold another story",
            "first_printings": len(members),
            "loose_members_read_too": loose,
            "job": len(members) + loose,
            "of_candidates": len(story),
        },
        "large_clusters": large,
    }


def order_of_key(found: dict):
    return lambda d: (found["dates"][d], found["ids"][d])


def body_links(found: dict, rng: random.Random, count: int) -> list:
    """Pairs that share a pair of their body's runs, from word 120, but sit in different eval
    A clusters, or in none: printings whose openings differ, for the recall probe."""
    cluster_of = {d: i for i, g in enumerate(found["frame"]) for d in g}
    holders = defaultdict(list)
    for doc, held in enumerate(found["body"]):
        for key in pairs(set(held)):
            holders[key].append(doc)
    links = set()
    for docs in holders.values():
        if 2 <= len(docs) <= BOILERPLATE:
            for a, b in pairwise(docs):
                if cluster_of.get(a, -1 - a) != cluster_of.get(b, -1 - b):
                    links.add((a, b))
    return rng.sample(sorted(links), min(count, len(links)))


def draw(found: dict) -> None:
    """The evaluation set and the dev set, drawn before any label or tuning. Each pair names
    its two candidates and its stratum; the texts go to the reading agents' batches, which
    name neither the stratum nor the similarity."""
    frame = [g for g in found["frame"]]
    clustered = sorted(d for g in frame for d in g)
    group_of = {d: g for g in frame for d in g}

    def partner(rng, doc):
        return rng.choice([m for m in group_of[doc] if m != doc])

    def per_candidate(rng, count, taken, band=None):
        out = []
        while len(out) < count:
            doc = rng.choice(clustered)
            other = partner(rng, doc)
            pair = tuple(sorted((doc, other)))
            if doc in taken or other in taken or pair in out:
                continue
            if band and not band[0] <= similarity(found, *pair)[1] < band[1]:
                continue
            out.append(pair)
            taken.update(pair)
        return out

    taken = set()
    rng = random.Random("2B.4 eval")
    strata = {"per candidate": per_candidate(rng, 200, taken)}
    picked = []
    while len(picked) < 100:
        group = rng.choice(frame)
        a, b = rng.sample(group, 2)
        if a not in taken and b not in taken:
            picked.append(tuple(sorted((a, b))))
            taken.update((a, b))
    strata["per cluster"] = picked
    strata["large cluster, least similar pair"] = [
        tuple(sorted(least_similar(found, g)))
        for g in sorted(frame, key=len, reverse=True)
        if len(g) >= LARGE
    ]
    taken.update(d for p in strata["large cluster, least similar pair"] for d in p)
    strata["near the threshold"] = per_candidate(rng, 80, taken, band=(0.2, 0.6))
    strata["body probe"] = [
        p for p in body_links(found, rng, 150) if not taken & set(p)
    ][:80]
    taken.update(d for p in strata["body probe"] for d in p)
    dev_rng = random.Random("2B.4 dev")
    dev = {
        "per candidate": per_candidate(dev_rng, 40, taken),
        "near the threshold": per_candidate(dev_rng, 120, taken, band=(0.1, 0.8)),
    }
    SETS.mkdir(parents=True, exist_ok=True)
    for name, chosen in (("eval", strata), ("dev", dev)):
        pairs_out = [
            {
                "pair": f"{name}-{n:04d}",
                "stratum": stratum,
                "a": found["ids"][a],
                "b": found["ids"][b],
                "similarity": similarity(found, a, b)
                if a in found["shingles"] and b in found["shingles"]
                else None,
                "label": None,
                "note": None,
            }
            for n, (stratum, (a, b)) in enumerate(
                ((s, p) for s, ps in chosen.items() for p in ps), 1
            )
        ]
        (SETS / f"{name}.json").write_text(json.dumps(pairs_out, indent=1) + "\n")
        print(name, {s: len(ps) for s, ps in chosen.items()})


def texts(root: Path, wanted: set) -> dict:
    """The paper, date, headline and first WORDS_SHOWN words of these candidates."""
    found = {}
    for path in sorted((root / "data" / "candidates").glob("*.jsonl.zst")):
        with zstandard.open(path, "rt") as rows:
            for row in map(json.loads, rows):
                if row["article_id"] in wanted:
                    words = (row["text"] or "").split()
                    found[row["article_id"]] = {
                        "paper": row["paper"],
                        "date": row["date"],
                        "headline": (row["headline"] or "")[:200],
                        "text": " ".join(words[:WORDS_SHOWN])
                        + (" […]" if len(words) > WORDS_SHOWN else ""),
                    }
    return found


def batches(root: Path, size: int = 50) -> None:
    """The reading agents' batches: every pair of both sets, shuffled together by seed, so a
    batch mixes strata and sets, with each printing's text and nothing else."""
    sets = [json.loads((SETS / f"{n}.json").read_text()) for n in ("eval", "dev")]
    every = [p for s in sets for p in s]
    shown = texts(root, {p[k] for p in every for k in ("a", "b")})
    random.Random("2B.4 batches").shuffle(every)
    BATCHES.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(every), size):
        batch = [
            {"pair": p["pair"], "first": shown[p["a"]], "second": shown[p["b"]]}
            for p in every[i : i + size]
        ]
        (BATCHES / f"batch-{i // size + 1:02d}.json").write_text(
            json.dumps(batch, indent=1) + "\n"
        )
    print(len(every), "pairs in", -(-len(every) // size), "batches")


def together(index: dict, story: list, pair: dict) -> bool:
    return story[index[pair["a"]]] == story[index[pair["b"]]]


def rate(hits: int, n: int) -> dict:
    if not n:
        return {"hits": 0, "n": 0}
    low, high = wilson(hits, n)
    return {"hits": hits, "n": n, "share": round(hits / n, 4), "low": low, "high": high}


def scored(index: dict, story: list, labelled: list) -> dict:
    """Precision and recall of same-story links: precision over the pairs the stories put
    together, recall over the pairs labelled one story."""
    kept = [p for p in labelled if together(index, story, p)]
    same = [p for p in labelled if p["label"] == "same"]
    return {
        "precision": rate(sum(p["label"] == "same" for p in kept), len(kept)),
        "recall": rate(sum(together(index, story, p) for p in same), len(same)),
        "false_merges": [p["pair"] for p in kept if p["label"] != "same"],
        "false_splits": [p["pair"] for p in same if not together(index, story, p)],
    }


def tune(found: dict) -> None:
    """Each threshold of GRID scored on the dev set: a false merge costs five false splits,
    since a story merged into another may never be read (decision 36)."""
    dev = [p for p in json.loads((SETS / "dev.json").read_text()) if p["label"]]
    index = {i: d for d, i in enumerate(found["ids"])}
    rows = []
    for threshold in GRID:
        story, _ = stories_at(found, threshold)
        result = scored(index, story, dev)
        cost = 5 * len(result["false_merges"]) + len(result["false_splits"])
        rows.append({"threshold": threshold, "cost": cost} | result)
        print(threshold, cost, len(result["false_merges"]), len(result["false_splits"]))
    (SETS / "tuning.json").write_text(json.dumps(rows, indent=1) + "\n")


def score(found: dict, threshold: float) -> None:
    """The stories at the tuned threshold, scored on the frozen evaluation set, by stratum."""
    path = SETS / "eval.json"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    frozen = json.loads((SETS / "frozen.json").read_text())
    assert digest == frozen["sha256"], "the evaluation set changed after it was frozen"
    labelled = json.loads(path.read_text())
    index = {i: d for d, i in enumerate(found["ids"])}
    story, match = stories_at(found, threshold)
    out = report(found, story, match, threshold)
    out["evaluation"] = {"sha256": digest} | {
        stratum: scored(index, story, [p for p in labelled if p["stratum"] == stratum])
        for stratum in dict.fromkeys(p["stratum"] for p in labelled)
    }
    REPORT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["evaluation"], indent=1)[:3000])


def main(run: str, root: Path = ROOT):
    found = features(root)
    if run == "build":
        story, match = stories_at(found, THRESHOLD)
        out = report(found, story, match, THRESHOLD)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(out, indent=1) + "\n")
        print(
            json.dumps(
                {k: v for k, v in out.items() if k != "large_clusters"}, indent=1
            )
        )
    elif run == "draw":
        draw(found)
        batches(root)
    elif run == "freeze":
        path = SETS / "eval.json"
        labelled = json.loads(path.read_text())
        assert all(p["label"] in ("same", "different") for p in labelled), (
            "unlabelled pairs"
        )
        frozen = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "pairs": len(labelled),
        }
        (SETS / "frozen.json").write_text(json.dumps(frozen, indent=1) + "\n")
        print(frozen)
    elif run == "tune":
        tune(found)
    elif run == "score":
        score(found, float(sys.argv[2]))


if __name__ == "__main__":
    main(sys.argv[1])
