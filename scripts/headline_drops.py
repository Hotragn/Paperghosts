"""The display headline's precision (Phase 2A): 200 of the lines it drops from candidate
headlines, the ones the site shows, sampled with a fixed seed across every year. Each is
judged by hand in eval/results/phase2a/headline-drops.json as "correct" (a masthead line,
or one with no letters) or "mis-drop" (headline text the site would lose). A second run
keeps the judgments and reports the precision with a 95% Wilson interval. With --same, it
runs the current rule on the judged lines instead of drawing new ones, and reports the
mis-drops it still makes and the correct drops it no longer makes.

    uv run python scripts/headline_drops.py [--same]
"""

import json
import random
import sys
from pathlib import Path

import zstandard

from paperghosts.ingest.headline import masthead_lines
from paperghosts.stats import wilson

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "eval" / "results" / "phase2a" / "headline-drops.json"
SEED, SIZE = "headline drops", 200


def dropped_lines():
    for path in sorted((ROOT / "data" / "candidates").glob("*.jsonl.zst")):
        with zstandard.open(path, "rt") as rows:
            for row in map(json.loads, rows):
                for line, dropped in masthead_lines(
                    row["headline"], row["paper"], row["date"]
                ):
                    if dropped:
                        yield {
                            "article_id": row["article_id"],
                            "date": row["date"],
                            "paper": row["paper"],
                            "line": line,
                            "headline": row["headline"],
                        }


def main():
    pool = list(dropped_lines())
    sample = random.Random(SEED).sample(pool, SIZE)
    known = {}
    if SAMPLE.exists():
        known = {
            (e["article_id"], e["line"]): e for e in json.loads(SAMPLE.read_text())
        }
    for e in sample:
        judged = known.get((e["article_id"], e["line"]), {})
        e["verdict"], e["note"] = judged.get("verdict"), judged.get("note")
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE.write_text(json.dumps(sample, indent=1) + "\n")
    print(f"{len(pool):,} lines dropped from candidate headlines; sampled {SIZE}")
    if all(e["verdict"] for e in sample):
        correct = sum(e["verdict"] == "correct" for e in sample)
        low, high = wilson(correct, SIZE)
        print(
            f"precision {correct}/{SIZE} = {correct / SIZE:.1%}, 95% interval {low:.1%}-{high:.1%}"
        )


def same_lines():
    judged = json.loads(SAMPLE.read_text())
    kept = {"correct": [], "mis-drop": []}
    for e in judged:
        dropped = masthead_lines(e["headline"], e["paper"], e["date"])
        if (e["line"], True) not in dropped:
            kept[e["verdict"]].append(e)
    total = {v: sum(e["verdict"] == v for e in judged) for v in kept}
    still = total["mis-drop"] - len(kept["mis-drop"])
    print(f"mis-drops still made: {still} of {total['mis-drop']}")
    print(f"correct drops now kept: {len(kept['correct'])} of {total['correct']}")
    for e in kept["correct"]:
        print(f"  {e['date']} {e['paper'][:40]!r}: {e['line']!r}")
    right = total["correct"] - len(kept["correct"])
    low, high = wilson(right, right + still)
    print(
        f"precision on the lines still dropped: {right}/{right + still} = {right / (right + still):.1%}, 95% interval {low:.1%}-{high:.1%}"
    )


if __name__ == "__main__":
    same_lines() if sys.argv[1:] == ["--same"] else main()
