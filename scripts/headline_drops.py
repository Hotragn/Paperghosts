"""The display headline's precision (Phase 2A): 200 of the lines it drops from candidate
headlines, the ones the site shows, sampled with a fixed seed across every year. Each is
judged by hand in eval/results/phase2a/headline-drops.json as "correct" (a masthead line,
or one with no letters) or "mis-drop" (headline text the site would lose). A second run
keeps the judgments and reports the precision with a 95% Wilson interval.

    uv run python scripts/headline_drops.py
"""

import json
import random
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
                for line, dropped in masthead_lines(row["headline"], row["paper"]):
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


if __name__ == "__main__":
    main()
