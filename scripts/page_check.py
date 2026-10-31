"""The page check's measurement, and which batch serves a page on a reel with more than one
(decision 35). Every request goes to tile.loc.gov one at a time, at least 3.5 s apart, cached
with its URL, date and status (crops.cached), and a run stops before CAP requests in all.

- reels: for a seeded sample of flagged reels, a candidate page with no batch path on each,
  and info.json on every batch the reel holds: which serve the page, and whether the rule's
  pick does.
- calibrate: seeded samples of candidate pages with a batch path whose member names another
  frame or reel, and as many whose member agrees, half of those of approximate size. Each gets
  info.json and the ALTO of the page its member names, in its batch path's batch.
- frames: for calibration's pages whose member names another frame, the batch path's own
  frame. The member's frame turned out to be the article's page, and the batch path's the one
  beside it, so calibration chose the text check's rule from these two runs.
- measure: other candidate pages whose member and batch path agree, half of approximate size.
  Each is checked by crops.page_check on its own frame (it should accept) and on the frame
  beside it, one up or down at random (it should reject), with the same article.
- look: the first box's crop for each own frame the measurement rejected by its text.

Writes eval/results/phase2b/page_check.json, one key per run.
"""

import json
import random
import re
import sys
from collections import defaultdict
from itertools import pairwise
from pathlib import Path

import zstandard

from paperghosts.ingest import crops, reels
from paperghosts.ingest.crops import BATCH_PATH, MEMBER, service, service_id
from paperghosts.stats import wilson

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results" / "phase2b" / "page_check.json"
# requests in all, the probes' and every earlier run's included
CAP = 600
# 2026-10-31: info.json twice and the ALTO twice, for the Litchfield page
PROBES = 4
# requests sent before this run: the probes, and the runs the results record
BEFORE = PROBES
# differ, exact, approximate
CALIBRATE = (20, 10, 10)
# exact, approximate: each checked on its own frame and on the one beside it
MEASURE = (45, 45)
# of each kind, split and reissue
REELS_DRAWN = 25


def gather(root: Path, reel_map: dict) -> dict:
    """The candidate pages, once each: those with a batch path whose member names another
    frame or reel, those whose member agrees (of exact and of approximate size), and those
    with no batch path on a flagged reel."""
    flagged = {(lccn, reel) for lccn, reel, _ in reels.flagged(reel_map)}
    found = {
        "differ": [],
        "exact": [],
        "approximate": [],
        "waiting": defaultdict(list),
        "scans": {},
    }
    seen = set()
    for path in sorted((root / "data" / "candidates").glob("*.jsonl.zst")):
        with zstandard.open(path, "rt") as rows:
            for row in map(json.loads, rows):
                if row["member"] in seen:
                    continue
                seen.add(row["member"])
                scan = row.get("scan") or {}
                bp = BATCH_PATH.search(scan.get("raw_data_loc") or "")
                member = MEMBER.search(row["member"])
                where = (member["lccn"], member["reel"], member["issue"], member["seq"])
                if bp is None:
                    if (member["lccn"], member["reel"]) in flagged:
                        found["waiting"][(member["lccn"], member["reel"])].append(
                            row["member"]
                        )
                        found["scans"][row["member"]] = scan
                elif (bp["lccn"], bp["reel"], bp["issue"], bp["seq"]) != where:
                    found["differ"].append(row["member"])
                elif scan.get("dimensions_approx"):
                    found["approximate"].append(row["member"])
                else:
                    found["exact"].append(row["member"])
    return found


def articles(root: Path, members: set) -> dict:
    """Each of these pages' candidate rows, by member."""
    rows_of = defaultdict(list)
    for path in sorted((root / "data" / "candidates").glob("*.jsonl.zst")):
        with zstandard.open(path, "rt") as rows:
            for row in map(json.loads, rows):
                if row["member"] in members:
                    rows_of[row["member"]].append(row)
    return rows_of


def tokens(text: str, shortest: int) -> list:
    return [t for t in re.findall(r"[a-z]+", text.lower()) if len(t) >= shortest]


def share(wanted: set, found: set):
    return round(len(wanted & found) / len(wanted), 4) if wanted else None


def pairs(words: list) -> set:
    return set(pairwise(words))


def scores(row: dict, info: dict, alto: dict) -> dict:
    """The text scores calibration compared: the share of the article's words of 5 or more
    letters found on the page, the share of its word pairs (of 3 or more letters each), and
    the share of its words found inside its own boxes on the page."""
    page = " ".join(w[4] for w in alto["words"])
    inside = crops.in_boxes(alto, info["height"], info["width"], row["bbox_list"])
    words = set(tokens(row["text"], 5))
    return {
        "article_words": len(words),
        "words_on_page": share(words, set(tokens(page, 5))),
        "pairs_on_page": share(pairs(tokens(row["text"], 3)), pairs(tokens(page, 3))),
        "words_in_boxes": share(words, inside),
    }


def asked() -> int:
    return BEFORE + sum(crops.SENT.values())


def members_page(member: str, row: dict) -> str:
    """The page the member names, in the batch path's batch."""
    page, bp = MEMBER.search(member), BATCH_PATH.search(row["scan"]["raw_data_loc"])
    return service(bp["batch"], page["lccn"], page["reel"], page["issue"], page["seq"])


def checked(named: str, member: str, row: dict, truth: str, verdict: bool) -> dict:
    """info.json and the ALTO for the page at named, and the page check's verdict on it."""
    info = crops.cached(f"{crops.IIIF}/{named}/info.json")
    entry = {
        "member": member,
        "article_id": row["article_id"],
        "truth": truth,
        "service": named,
        "batch_path": row["scan"]["raw_data_loc"],
        "recorded_size": [row["scan"].get("height"), row["scan"].get("width")],
        "approximate": bool(row["scan"].get("dimensions_approx")),
        "info_status": info["status"],
    }
    if info["status"] != 200:
        if verdict:
            entry["verdict"] = crops.page_check(
                named, row["scan"], row["bbox_list"], row["text"]
            )
        return entry
    entry["info_size"] = [info["body"]["height"], info["body"]["width"]]
    alto = crops.cached(crops.alto_url(named), keep=crops.alto_words)
    entry["alto_status"] = alto["status"]
    if alto["status"] == 200:
        entry |= scores(row, info["body"], alto["body"])
    if verdict:
        entry["verdict"] = crops.page_check(
            named, row["scan"], row["bbox_list"], row["text"]
        )
    return entry


def calibrate_run(root: Path, found: dict) -> list:
    differ, exact, approximate = CALIBRATE
    rng = random.Random("2B.3 calibrate")
    drawn = {
        "another frame": rng.sample(sorted(set(found["differ"])), differ),
        "same page": rng.sample(sorted(set(found["exact"])), exact)
        + rng.sample(sorted(set(found["approximate"])), approximate),
    }
    rows_of = articles(root, {m for ms in drawn.values() for m in ms})
    entries = []
    for truth, members in drawn.items():
        for member in members:
            if asked() + 2 > CAP:
                raise SystemExit(f"stopped before the cap of {CAP} requests")
            row = rng.choice(sorted(rows_of[member], key=lambda r: r["article_id"]))
            named = members_page(member, row)
            entries.append(checked(named, member, row, truth, False))
    return entries


def frames_run(root: Path, results: dict) -> list:
    """For each calibration page whose member names another frame: the batch path's own
    frame, to see which of the two holds the article."""
    wanted = [
        e
        for e in results["calibrate"]
        if e["truth"] == "another frame" and e["info_status"] == 200
    ]
    rows_of = articles(root, {e["member"] for e in wanted})
    entries = []
    for e in wanted:
        if asked() + 2 > CAP:
            raise SystemExit(f"stopped before the cap of {CAP} requests")
        row = next(
            r for r in rows_of[e["member"]] if r["article_id"] == e["article_id"]
        )
        own = service_id(row["scan"]["raw_data_loc"])
        entries.append(checked(own, e["member"], row, "the batch path's frame", False))
    return entries


def beside(raw_data_loc: str, step: int) -> str:
    """The frame one up or down from the batch path's, in its batch."""
    page = BATCH_PATH.search(raw_data_loc)
    seq = page["seq"]
    frame = int(seq) + (step if int(seq) + step > 0 else 1)
    return service(
        page["batch"],
        page["lccn"],
        page["reel"],
        page["issue"],
        f"{frame:0{len(seq)}d}",
    )


def measure_run(root: Path, found: dict, taken: set) -> list:
    exact, approximate = MEASURE
    rng = random.Random("2B.3 measure")
    members = rng.sample(sorted(set(found["exact"]) - taken), exact) + rng.sample(
        sorted(set(found["approximate"]) - taken), approximate
    )
    rows_of = articles(root, set(members))
    entries = []
    for member in members:
        if asked() + 4 > CAP:
            raise SystemExit(f"stopped before the cap of {CAP} requests")
        row = rng.choice(sorted(rows_of[member], key=lambda r: r["article_id"]))
        own = service_id(row["scan"]["raw_data_loc"])
        other = beside(row["scan"]["raw_data_loc"], rng.choice((-1, 1)))
        entries.append(checked(own, member, row, "same page", True))
        entries.append(checked(other, member, row, "the frame beside it", True))
    return entries


def look_run(root: Path, results: dict) -> list:
    """The first box's crop, for each own frame the measured check rejected by its text, to
    see which is wrong: the check, or the page both sources name."""
    wanted = [
        e
        for e in results["measure"]
        if e["truth"] == "same page" and e["verdict"] not in (None, crops.NO_SUCH_PAGE)
    ]
    rows_of = articles(root, {e["member"] for e in wanted})
    entries = []
    for e in wanted:
        row = next(
            r for r in rows_of[e["member"]] if r["article_id"] == e["article_id"]
        )
        [url] = crops.crop_urls(e["service"], row["bbox_list"][:1])
        entries.append(
            {
                "service": e["service"],
                "crop": str(crops.crop(url).relative_to(ROOT)),
                "text": row["text"][:300],
            }
        )
    return entries


def reels_run(found: dict, reel_map: dict) -> list:
    rng = random.Random("2B.3 reels")
    kinds = defaultdict(list)
    for lccn, reel, batches in reels.flagged(reel_map):
        if found["waiting"].get((lccn, reel)):
            names = {reels.VERSION.sub("", b) for b in batches}
            kinds["reissue" if len(names) == 1 else "split"].append((lccn, reel))
    entries = []
    for kind in ("split", "reissue"):
        for lccn, reel in rng.sample(sorted(kinds[kind]), REELS_DRAWN):
            batches = reel_map[lccn][reel]
            member = rng.choice(sorted(found["waiting"][(lccn, reel)]))
            page = MEMBER.search(member)
            if asked() + len(batches) > CAP:
                raise SystemExit(f"stopped before the cap of {CAP} requests")
            serve = {}
            for batch in batches:
                named = service(
                    batch, page["lccn"], page["reel"], page["issue"], page["seq"]
                )
                info = crops.cached(f"{crops.IIIF}/{named}/info.json")
                body = info["body"] or {}
                serve[batch] = {
                    "status": info["status"],
                    "size": [body.get("height"), body.get("width")],
                }
            scan = found["scans"][member]
            entries.append(
                {
                    "kind": kind,
                    "member": member,
                    "recorded_size": [scan.get("height"), scan.get("width")],
                    "approximate": bool(scan.get("dimensions_approx")),
                    "picked": reels.pick(batches, page["issue"]),
                    "batches": serve,
                }
            )
    return entries


def rate(hits: int, n: int) -> dict:
    if not n:
        return {"hits": 0, "n": 0}
    low, high = wilson(hits, n)
    return {"hits": hits, "n": n, "share": round(hits / n, 4), "low": low, "high": high}


def summary(results: dict, probes: int = PROBES) -> dict:
    """The headline numbers, counted from the rows: the page check's false accepts and false
    rejects, what size alone would accept, which frame held the article where the member and
    the batch path differ, and how often the rule's pick serves a flagged reel's page."""
    measure = results.get("measure", [])
    beside = [e for e in measure if e["truth"] == "the frame beside it"]
    there = [e for e in beside if e["info_status"] == 200]
    own = [e for e in measure if e["truth"] == "same page"]
    served = [e for e in own if e["info_status"] == 200]

    def by_size(e):
        if e["approximate"]:
            return e["verdict"] != "boxes off the page"
        return e["recorded_size"] == e["info_size"]

    differ = [
        e
        for e in results.get("calibrate", [])
        if e["truth"] == "another frame" and e["info_status"] == 200
    ]
    reel_rows = results.get("reels", [])
    return {
        "false_accepts": rate(sum(e["verdict"] is None for e in beside), len(beside)),
        "false_accepts_where_the_frame_exists": rate(
            sum(e["verdict"] is None for e in there), len(there)
        ),
        "size_alone_accepts_where_the_frame_exists": rate(
            sum(map(by_size, there)), len(there)
        )
        | {
            kind: rate(
                sum(by_size(e) for e in there if e["approximate"] == approximate),
                sum(e["approximate"] == approximate for e in there),
            )
            for kind, approximate in (("exact", False), ("approximate", True))
        },
        "false_rejects_where_the_page_exists": rate(
            sum(e["verdict"] is not None for e in served), len(served)
        ),
        "own_frames_no_longer_served": sum(e["info_status"] != 200 for e in own),
        "member_frames_of_the_recorded_size": rate(
            sum(e["recorded_size"] == e["info_size"] for e in differ), len(differ)
        ),
        "batch_path_frames_of_the_recorded_size": rate(
            sum(
                e["recorded_size"] == e.get("info_size")
                for e in results.get("frames", [])
            ),
            len(results.get("frames", [])),
        ),
        "reels_first_pick_serves": rate(
            sum(e["batches"][e["picked"]]["status"] == 200 for e in reel_rows),
            len(reel_rows),
        ),
        "reels_some_batch_serves": rate(
            sum(
                any(b["status"] == 200 for b in e["batches"].values())
                for e in reel_rows
            ),
            len(reel_rows),
        ),
        "requests": probes + sum(r["sent"] for r in results.get("requests", [])),
    }


def main(run: str, root: Path = ROOT):
    global BEFORE
    # this step's rule: one request in 3.5 s, to any host
    crops.GAPS["tile.loc.gov"] = 3.5
    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    runs = results.setdefault("requests", [])
    BEFORE = PROBES + sum(r["sent"] for r in runs)
    try:
        reel_map = reels.load()
        found = gather(root, reel_map)
        if run == "reels":
            results[run] = reels_run(found, reel_map)
        elif run == "frames":
            results[run] = frames_run(root, results)
        elif run == "look":
            results[run] = look_run(root, results)
        elif run == "calibrate":
            results[run] = calibrate_run(root, found)
        else:
            taken = {e["member"] for e in results.get("calibrate", [])}
            results[run] = measure_run(root, found, taken)
    finally:  # what a run sent is recorded even when it stops
        runs.append(
            {
                "run": run,
                "sent": sum(crops.SENT.values()),
                "by_host": dict(crops.SENT),
                "cache_hits": crops.COUNTS["cache_hits"],
                "errors_not_cached": crops.COUNTS["errors"],
            }
        )
        results["summary"] = summary(results)
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        RESULTS.write_text(json.dumps(results, indent=1) + "\n")
        print(run, runs[-1], "in all, with the probes:", asked())


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT)
