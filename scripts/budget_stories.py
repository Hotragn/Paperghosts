"""Stories per report printing, from the judged reports (BUDGET.md's third scenario).

Each judged report is a printing drawn at random from its pool, so it counts as 1/k of a story
when its story holds k printings (decision 36's stories, at the tuned threshold; eval A's
clusters before). The ratio is the mean of 1/k, taken by pool:
- v1's candidates: eval A's 7
- the candidates v2 added: 2A.8's 14, and the 3 of the screen's 4 that v2 makes candidates

Writes eval/results/phase2b/budget_stories.json."""

import json
from collections import Counter
from datetime import UTC, datetime

from budget_probe import (
    DATA,
    PRINTINGS,
    RESULTS,
    STORIES_PER_PRINTING,
    judged_reports,
)
from clusters import THRESHOLD, features, stories_at

OUT = RESULTS / "phase2b" / "budget_stories.json"
# the tops and the points of decision 27's and decision 31's estimates, in printings
POOLS = {
    "v1's candidates": {"top": 74_027, "point": 36_766, "from": ["eval A"]},
    "the candidates v2 added": {
        "top": 21_176,
        "point": 12_996,
        "from": ["2A.8", "screen"],
    },
}


def main():
    found = features()
    story, _ = stories_at(found, THRESHOLD)
    held = Counter(story)
    size_of = {article: held[story[d]] for d, article in enumerate(found["ids"])}
    judged = judged_reports()

    pools = {}
    for name, pool in POOLS.items():
        reports = [
            {"article_id": a, "from": source, "printings": size_of[a]}
            for source in pool["from"]
            for a in judged[source]
            if a in size_of  # the screen's 1918 scout isn't a v2 candidate
        ]
        ratio = sum(1 / r["printings"] for r in reports) / len(reports)
        pools[name] = {
            "reports": reports,
            "stories_per_printing": round(ratio, 4),
            "stories": {
                "top": round(pool["top"] * ratio),
                "point": round(pool["point"] * ratio),
            },
        }
    top = sum(p["stories"]["top"] for p in pools.values())
    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pools": pools,
        "top_of_the_range": {
            "printings": PRINTINGS,
            "stories": top,
            "stories_at_v1s_ratio": round(PRINTINGS * STORIES_PER_PRINTING),
        },
        "point": {"stories": sum(p["stories"]["point"] for p in pools.values())},
    }
    OUT.write_text(json.dumps(report, indent=1) + "\n")
    for name, p in pools.items():
        sizes = [r["printings"] for r in p["reports"]]
        print(
            f"{name}: {len(sizes)} reports, printings {sizes}, "
            f"{p['stories_per_printing']:.3f} stories per printing"
        )
    print(f"top of the range: {top:,} stories of {PRINTINGS:,} printings")
    print(f"wrote {OUT.relative_to(DATA.parent)}")


if __name__ == "__main__":
    main()
