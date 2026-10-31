"""The Morgue's reports in Atlas: the 78 labelled reports of web/public/reports.json upserted into
paperghosts.reports, each built as the planned Report document and checked by its model, so Atlas's
validator and the existing reports_search index take them as they are. Insert and replace only;
nothing is dropped or deleted. The label is the frozen hand label (eval/gold), not the reader's,
and versions.model says so. No report has coordinates yet, so none has a location.

  uv run python scripts/load_demo_atlas.py
Writes eval/results/atlas_demo.json: counts, storage and the Search indexes' states.
"""

import json
import subprocess
import time

from label_gold import ROOT, articles
from pymongo import MongoClient

from paperghosts.config import setting
from paperghosts.ingest import lexicon
from paperghosts.schemas import Report
from paperghosts.store.db_init import DATABASE
from paperghosts.store.printings import printing

DEMO = ROOT / "web" / "public" / "reports.json"
RESULT = ROOT / "eval" / "results" / "atlas_demo.json"
REQUIRED = ("place", "seen", "outcome")
OPTIONAL = ("specific_place", "place_type", "precision")
TERMS = {*lexicon.GHOST, *lexicon.TOGETHER}


def stated(field: dict | None) -> dict:
    """A hand label's field as the schema stores it: a value only with its verified quote."""
    if not field or not field["verified"]:
        return {"verified": False, "score": 0.0}
    return {
        "value": field["value"],
        "quote": field["quote"],
        "verified": True,
        "score": 1.0,
    }


def document(entry: dict, row: dict, code: str) -> dict:
    date = entry["date"]
    title = entry["headline"].strip() or entry["text"][:80]
    fields = {name: stated(entry[name]) for name in REQUIRED}
    fields |= {
        n: stated(entry[n]) for n in OPTIONAL if entry[n] and entry[n]["verified"]
    }
    fields["people"] = [stated(p) for p in entry["people"] if p["verified"]]
    printed = printing(row) | {
        k: v
        for k, v in (
            ("place", entry["printed_in"]["place"]),
            ("state", entry["printed_in"]["state"]),
        )
        if v
    }
    story_state = entry["place_state"]
    found = Report.model_validate(
        {
            "_id": f"r_{entry['article_id']}",
            "primary_article_id": entry["article_id"],
            "printings": [printed],
            "headline": entry["headline"],
            "text": entry["text"],
            "display_headline": title,
            "date": date,
            "year": int(date[:4]),
            "month_day": date[5:],
            "decade": int(date[:4]) // 10 * 10,
            "kind": "report",
            "fields": fields,
            "state": story_state["value"]
            if story_state and story_state["verified"]
            else None,
            "versions": {
                "code": code,
                "model": "hand label: eval/gold, frozen (Claude, first pass)",
            },
            "lexicon_terms": sorted(t for t in row.get("terms") or {} if t in TERMS)
            or ["ghost"],
        }
    )
    return found.model_dump(by_alias=True, exclude_none=True)


def main() -> None:
    entries = json.loads(DEMO.read_text())
    rows = articles()
    code = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    docs = [document(e, rows[e["article_id"]], code) for e in entries]
    started = time.time()
    with MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        reports = client[DATABASE]["reports"]
        changed = [reports.replace_one({"_id": d["_id"]}, d, upsert=True) for d in docs]
        seconds = time.time() - started
        stats = client[DATABASE].command("collStats", "reports")
        searches = [
            {
                "name": s["name"],
                "status": s.get("status"),
                "queryable": s.get("queryable"),
            }
            for s in reports.list_search_indexes()
        ]
        found = {
            "documents": reports.count_documents({}),
            "demo_reports": len(docs),
            "inserted": sum(c.upserted_id is not None for c in changed),
            "replaced": sum(c.modified_count for c in changed),
            "load_seconds": round(seconds, 1),
            "storage_kb": round(stats["storageSize"] / 1024, 1),
            "data_kb": round(stats["size"] / 1024, 1),
            "index_kb": round(stats["totalIndexSize"] / 1024, 1),
            "search_indexes": searches,
            "with_location": reports.count_documents({"location": {"$exists": True}}),
            "code": code,
        }
    RESULT.write_text(json.dumps(found, indent=1) + "\n")
    print(json.dumps(found, indent=1))


if __name__ == "__main__":
    main()
