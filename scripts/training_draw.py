"""The teacher's training draw (2C.3, the plan's 2C step 4), from split.json's pool only.

Stratified as gold is (decision 37's ALLOCATION, scaled), so reports and every hard slice are
well represented. Within each stratum the draw is systematic in date order and seeded, and it
takes at most one printing per story: an article whose group is already drawn is passed over.

  draw N     N articles into eval/results/phase2c/training_draw.json
  check      the draw against the split's rules, and every drawn text against gold and dev by the
             stricter rule (at least 4 shared runs and 0.05 of the shorter's), into
             eval/results/phase2c/draw_leakage.json; exits 0 only if it holds
"""

import json
import random
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

from check_leakage import SPLIT, between, whole_texts
from credit_check import loaded
from gold_draw import ALLOCATION, NEAR, strata_in, systematic
from label_gold import ROOT

DRAW = ROOT / "eval" / "results" / "phase2c" / "training_draw.json"
CHECKED = ROOT / "eval" / "results" / "phase2c" / "draw_leakage.json"
STRICT = {
    "leak": 0.05,
    "fewest": 4,
}  # the EM's call: stricter than the split's 0.10 and 5


def allocation(n: int) -> dict:
    """Gold's allocation scaled to n articles, by largest remainder."""
    total = sum(g for g, _ in ALLOCATION.values())
    exact = {name: n * g / total for name, (g, _) in ALLOCATION.items()}
    sizes = {name: int(x) for name, x in exact.items()}
    for name in sorted(exact, key=lambda k: exact[k] - sizes[k], reverse=True)[
        : n - sum(sizes.values())
    ]:
        sizes[name] += 1
    return sizes


def drawn(units: dict, sizes: dict, group: dict, seed: str) -> list:
    """Each stratum's share, systematic in date order, at most one printing per story: each
    stratum keeps its earliest printing of each story not already drawn, then draws from those.

    units maps a stratum to its (date, article id) pairs; group maps an article to its story."""
    rng, taken, picked = random.Random(seed), set(), []
    for name, size in sizes.items():
        first = {}
        for date, aid in sorted(units.get(name, [])):
            if group[aid] not in taken:
                first.setdefault(group[aid], (date, aid))
        stories = sorted(first.values())
        if not size or not stories:
            continue
        for _, aid in systematic(stories, min(size, len(stories)), rng):
            taken.add(group[aid])
            picked.append((aid, name))
    return picked


def problems(draw: list, split: dict, group: dict) -> dict:
    """The split's rules on a draw: every article in the pool, and one printing per story."""
    out = set(split["out_of_pool"])
    stories = Counter(group.get(aid, aid) for aid in draw)
    return {
        "outside_the_pool": sorted(
            aid for aid in draw if aid in out or aid not in group
        ),
        "stories_drawn_twice": sorted(g for g, n in stories.items() if n > 1),
    }


def main() -> None:
    run, *rest = sys.argv[1:]
    made = loaded()
    group = dict(zip(made["ids"], made["group"], strict=True))
    split = json.loads(SPLIT.read_text())
    if run == "draw":
        n = int(rest[0])
        candidate = dict(zip(made["ids"], made["candidate"], strict=True))
        paths = sorted((ROOT / "data" / "candidates").glob("*.jsonl.zst"))
        units = {}
        with ProcessPoolExecutor(8) as workers:
            for part in workers.map(strata_in, paths):
                for aid, name in part:
                    if aid in group:
                        units.setdefault(name, []).append((aid.split("_")[1], aid))
        units[NEAR] = [
            (aid.split("_")[1], aid) for aid, c in candidate.items() if not c
        ]
        picked = drawn(units, allocation(n), group, f"2C.3 training draw {n}")
        DRAW.write_text(
            json.dumps(
                {
                    "size": len(picked),
                    "seed": f"2C.3 training draw {n}",
                    "strata": dict(Counter(name for _, name in picked)),
                    "drawn_from": {name: len(v) for name, v in units.items()},
                    "draw": [
                        {"article_id": aid, "stratum": name} for aid, name in picked
                    ],
                },
                indent=1,
            )
            + "\n"
        )
        print(len(picked), "drawn;", dict(Counter(name for _, name in picked)))
    elif run == "check":
        draw = [d["article_id"] for d in json.loads(DRAW.read_text())["draw"]]
        held = {i["article_id"] for name in ("gold", "dev") for i in split[name]}
        found = problems(draw, split, group)
        texts, held_texts = whole_texts(ROOT, set(draw)), whole_texts(ROOT, held)
        found["reprints_of_gold_or_dev"] = between(texts, held_texts, **STRICT)
        found |= {"draw": len(draw), "texts_read": len(texts), "rule": STRICT}
        found["passes"] = not any(
            found[k]
            for k in (
                "outside_the_pool",
                "stories_drawn_twice",
                "reprints_of_gold_or_dev",
            )
        ) and len(texts) == len(draw)
        CHECKED.write_text(json.dumps(found, indent=1) + "\n")
        print(
            json.dumps(
                {k: v if not isinstance(v, list) else len(v) for k, v in found.items()},
                indent=1,
            )
        )
        sys.exit(0 if found["passes"] else 1)


if __name__ == "__main__":
    main()
