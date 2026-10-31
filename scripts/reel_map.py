"""The reel-to-batch map (decision 35), built from the batch paths in the candidates and samples,
and its check: each issue is hidden in turn, all its pages at once, and its batch is picked from
the rest of its reel. Writes the map to data/reels/map.json and the report to
eval/results/phase2b/reels.json. It asks loc.gov nothing."""

import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

import zstandard

from paperghosts.ingest import reels
from paperghosts.ingest.crops import (
    BATCH_PATH,
    MEMBER,
    batch_path_service,
    service_id,
)
from paperghosts.stats import wilson

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "eval" / "results" / "phase2b" / "reels.json"


def pages(root: Path) -> dict:
    """Each page of the candidates and samples once, by member: its batch path's (batch, lccn,
    reel, issue), its member's (lccn, reel) and issue, how many candidates it holds, and
    whether decision 35's frame rule changes its stored service."""
    found = {}
    for pool in ("candidates", "samples"):
        for path in sorted((root / "data" / pool).glob("*.jsonl.zst")):
            with zstandard.open(path, "rt") as rows:
                for row in map(json.loads, rows):
                    page = found.get(row["member"])
                    if page is None:
                        scan = row.get("scan") or {}
                        bp = BATCH_PATH.search(scan.get("raw_data_loc") or "")
                        member = MEMBER.search(row["member"])
                        page = found[row["member"]] = {
                            "path": (bp["batch"], bp["lccn"], bp["reel"], bp["issue"])
                            if bp
                            else None,
                            "reel": (member["lccn"], member["reel"]),
                            "issue": member["issue"],
                            "candidates": 0,
                            "changed": bool(bp)
                            and batch_path_service(row["member"], bp.string)
                            != service_id(bp.string),
                        }
                    page["candidates"] += pool == "candidates"
    return found


def held_out(reel_map: dict):
    """(lccn, reel, issue, the batches holding it, the batch picked with the whole issue hidden),
    for every issue of every reel; picked is None where the reel holds no other issue."""
    for lccn, on in reel_map.items():
        for reel, batches in on.items():
            holding = defaultdict(set)
            for batch, issues in batches.items():
                for issue in issues:
                    holding[issue].add(batch)
            for issue, truth in holding.items():
                rest = {
                    b: [i for i in held if i != issue] for b, held in batches.items()
                }
                rest = {b: held for b, held in rest.items() if held}
                yield (
                    lccn,
                    reel,
                    issue,
                    truth,
                    reels.pick(rest, issue) if rest else None,
                )


def coverage(found: dict, reel_map: dict) -> dict:
    """How many candidates with no batch path sit on a reel the map holds."""
    covered = uncovered = 0
    left, no_reel = set(), 0
    for page in found.values():
        if page["path"] or not page["candidates"]:
            continue
        lccn, reel = page["reel"]
        if reel in reel_map.get(lccn, {}):
            covered += page["candidates"]
        else:
            uncovered += page["candidates"]
            left.add(page["reel"])
            no_reel += page["candidates"] * (reel == "no_reel")
    total = covered + uncovered
    return {
        "candidates_with_no_batch_path": total,
        "covered": covered,
        "covered_share": round(covered / total, 4),
        "not_covered": uncovered,
        "not_covered_reels": len(left),
        "not_covered_with_no_reel_in_their_member": no_reel,
    }


def rate(hits: int, n: int) -> dict:
    if not n:
        return {"hits": 0, "n": 0}
    low, high = wilson(hits, n)
    return {"hits": hits, "n": n, "share": round(hits / n, 4), "low": low, "high": high}


def iso(issue: str) -> str:
    return date.fromordinal(reels.day(issue)).isoformat()


def check(found: dict, reel_map: dict) -> dict:
    """The hidden-issue check: its hit rate over issues, overall and on flagged reels, by batch
    and by batch name (a reissue's versions taken as one), and the pages and candidates behind
    them."""
    flagged = {(lccn, reel) for lccn, reel, _ in reels.flagged(reel_map)}
    picked = {}
    counts = defaultdict(Counter)
    for lccn, reel, issue, truth, batch in held_out(reel_map):
        picked[(lccn, reel, issue)] = batch
        counts["all"]["in_more_than_one_batch"] += len(truth) > 1
        for group in ("all", "flagged") if (lccn, reel) in flagged else ("all",):
            tally = counts[group]
            if batch is None:
                tally["untested"] += 1
                continue
            tally["tested"] += 1
            tally["hits"] += truth == {batch}
            tally["name_hits"] += {reels.VERSION.sub("", t) for t in truth} == {
                reels.VERSION.sub("", batch)
            }
    pages_hit = Counter()
    for page in found.values():
        if not page["path"]:
            continue
        batch, lccn, reel, issue = page["path"]
        guess = picked[(lccn, reel, issue)]
        if guess is None:
            continue
        group = "flagged" if (lccn, reel) in flagged else "single"
        pages_hit[f"{group}_pages"] += 1
        pages_hit[f"{group}_pages_hit"] += guess == batch
        pages_hit[f"{group}_candidates"] += page["candidates"]
        pages_hit[f"{group}_candidates_hit"] += page["candidates"] * (guess == batch)
    one_issue = sum(
        len({i for held in batches.values() for i in held}) == 1
        for on in reel_map.values()
        for batches in on.values()
    )
    return (
        {
            "issues_in_more_than_one_batch": counts["all"]["in_more_than_one_batch"],
        }
        | {
            group: {
                "issues_tested": tally["tested"],
                "issues_untested": tally["untested"],
                "hit": rate(tally["hits"], tally["tested"]),
                "hit_by_batch_name": rate(tally["name_hits"], tally["tested"]),
            }
            for group, tally in counts.items()
        }
        | {
            "reels_with_one_issue_untestable": one_issue,
            "pages": dict(pages_hit),
        }
    )


def frame_rule(found: dict) -> dict:
    """The candidates whose stored service decision 35's frame rule changes, by batch: those
    on a page whose member names another frame of its batch path's reel and issue."""
    by_batch = Counter()
    pages_hit = 0
    for page in found.values():
        if page.get("changed") and page["candidates"]:
            by_batch[page["path"][0]] += page["candidates"]
            pages_hit += 1
    return {
        "candidates_whose_service_changes": sum(by_batch.values()),
        "pages_with_candidates": pages_hit,
        "by_batch": dict(by_batch.most_common()),
    }


def flagged_reels(found: dict, reel_map: dict) -> list:
    """Every reel with more than one batch, each batch with its date range on the reel, and
    the candidates with no batch path that sit on it."""
    waiting = Counter()
    for page in found.values():
        if not page["path"]:
            waiting[page["reel"]] += page["candidates"]
    return [
        {
            "lccn": lccn,
            "reel": reel,
            "kind": "reissue"
            if len({reels.VERSION.sub("", b) for b in batches}) == 1
            else "split",
            "batches": [
                {
                    "batch": batch,
                    "first": iso(issues[0]),
                    "last": iso(issues[-1]),
                    "issues": len(issues),
                }
                for batch, issues in sorted(batches.items(), key=lambda b: b[1][0])
            ],
            "candidates_with_no_batch_path": waiting[(lccn, reel)],
        }
        for lccn, reel, batches in reels.flagged(reel_map)
    ]


def main(root: Path = ROOT):
    found = pages(root)
    paths = [p["path"] for p in found.values() if p["path"]]
    reel_map = reels.build(paths)
    from_candidates = reels.build(
        p["path"] for p in found.values() if p["path"] and p["candidates"]
    )
    reels.MAP.parent.mkdir(parents=True, exist_ok=True)
    reels.MAP.write_text(json.dumps(reel_map, separators=(",", ":")))
    flagged = flagged_reels(found, reel_map)
    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pages": len(found),
        "pages_with_a_batch_path": len(paths),
        "reels": sum(len(on) for on in reel_map.values()),
        "issues": len({(p[1], p[2], p[3]) for p in paths}),
        "coverage_from_candidates_only": coverage(found, from_candidates),
        "coverage": coverage(found, reel_map),
        "hidden_issues": check(found, reel_map),
        "frame_rule": frame_rule(found),
        "flagged": {
            "reels": len(flagged),
            "split": sum(f["kind"] == "split" for f in flagged),
            "reissue": sum(f["kind"] == "reissue" for f in flagged),
            "candidates_with_no_batch_path": sum(
                f["candidates_with_no_batch_path"] for f in flagged
            ),
            "list": flagged,
        },
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1) + "\n")
    shown = {k: v for k, v in report.items() if k not in ("flagged", "frame_rule")}
    print(json.dumps(shown, indent=1))
    rule = report["frame_rule"]
    print(
        "frame rule:",
        rule["candidates_whose_service_changes"],
        "candidates on",
        rule["pages_with_candidates"],
        "pages, in",
        len(rule["by_batch"]),
        "batches; the most:",
        list(rule["by_batch"].items())[:5],
    )
    print({k: v for k, v in report["flagged"].items() if k != "list"})


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT)
