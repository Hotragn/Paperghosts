"""Ghosts like this one, for the static Morgue: for each report in web/public/reports.json, the five
reports Atlas Search's moreLikeThis ranks closest (scripts/query_demo_atlas.like), written back as
its `like` list of article ids with scores. The answers are Atlas's; the page reads them offline.

  uv run python scripts/export_like.py
"""

import json
import time

from export_demo import WEB
from pymongo import MongoClient
from query_demo_atlas import like

from paperghosts.config import setting
from paperghosts.store.db_init import DATABASE


def main() -> None:
    path = WEB / "reports.json"
    reports = json.loads(path.read_text())
    started, timings = time.time(), []
    with MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        stored = client[DATABASE]["reports"]
        for r in reports:
            doc = stored.find_one(
                {"_id": f"r_{r['article_id']}"}, {"headline": 1, "text": 1}
            )
            t = time.perf_counter()
            found = list(stored.aggregate(like(doc)))
            timings.append((time.perf_counter() - t) * 1000)
            r["like"] = [
                {
                    "article_id": f["_id"].removeprefix("r_"),
                    "score": round(f["score"], 2),
                }
                for f in found
            ]
    path.write_text(json.dumps(reports, indent=1) + "\n")
    timings.sort()
    print(
        f"{len(reports)} reports, {sum(len(r['like']) for r in reports)} neighbours, "
        f"median {timings[len(timings) // 2]:.0f} ms, slowest {timings[-1]:.0f} ms, {time.time() - started:.0f} s in all"
    )


if __name__ == "__main__":
    main()
