"""Stories per report printing, from the judged reports (BUDGET.md's third scenario).

Each judged report is a printing drawn at random from its pool, so it counts as 1/k of a story
when its v2 reprint cluster holds k printings. The ratio is the mean of 1/k, taken by pool:
- v1's candidates: eval A's 7
- the candidates v2 added: 2A.8's 14, and the 3 of the screen's 4 that v2 makes candidates

Writes eval/results/phase2b/budget_stories.json."""

import json
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime

from budget_probe import (
    DATA,
    PRINTINGS,
    RESULTS,
    STORIES_PER_PRINTING,
    judged_reports,
    year_keys,
)

from paperghosts.cluster.reprints import clusters

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
    counts = {
        c["year"]: c["candidates"]
        for c in (json.loads(p.read_text()) for p in (DATA / "counts").glob("*.json"))
    }
    years = sorted(y for y in counts if counts[y])
    doc_keys, ids = [], []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for _, found, named, _ in pool.map(year_keys, years):
            doc_keys += found
            ids += named
    size_of = {}
    for group in clusters(doc_keys, least=2):
        for doc in group:
            size_of[doc] = len(group)
    index_of = {article: i for i, article in enumerate(ids)}
    judged = judged_reports()

    pools = {}
    for name, pool in POOLS.items():
        reports = [
            {"article_id": a, "from": source, "printings": size_of.get(index_of[a], 1)}
            for source in pool["from"]
            for a in judged[source]
            if a in index_of  # the screen's 1918 scout isn't a v2 candidate
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
