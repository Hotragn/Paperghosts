"""A real Atlas Search query over the Morgue's reports, through the existing reports_search index.

  uv run python scripts/query_demo_atlas.py "<town or word>"   fuzzy, so a word the OCR misread
                                                               ("knocklngs") still finds its report
  uv run python scripts/query_demo_atlas.py --like ARTICLE_ID  ghosts like this one: moreLikeThis
                                                               on its headline and text
Prints each match with its date, paper, story place, score and the matched words, and the round
trip in milliseconds.
"""

import sys
import time

import sentry_sdk
from pymongo import MongoClient

from paperghosts.config import setting
from paperghosts.observability.sentry import atlas_query, init_sentry
from paperghosts.store.db_init import DATABASE
from paperghosts.store.search import fuzzy, like


def matched(found: dict) -> str:
    words = {
        t["value"]
        for h in found.get("highlights") or []
        for t in h["texts"]
        if t["type"] == "hit"
    }
    return ", ".join(sorted(words)[:6])


def main(args: list) -> None:
    init_sentry("pipeline")
    with MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        reports = client[DATABASE]["reports"]
        if args[0] == "--like":
            doc = reports.find_one({"_id": f"r_{args[1]}"}, {"headline": 1, "text": 1})
            if doc is None:
                sys.exit(f"{args[1]} is not in the Morgue")
            print(
                f"ghosts like {doc['headline'].splitlines()[0] if doc['headline'] else args[1]}:"
            )
            pipeline = like(doc)
        else:
            print(f"search: {args[0]!r}, fuzzy up to 2 edits")
            pipeline = fuzzy(args[0])
        kind = "reports more_like_this" if args[0] == "--like" else "reports fuzzy"
        with atlas_query(kind, "query_demo_atlas"):
            started = time.perf_counter()
            results = list(reports.aggregate(pipeline))
            ms = (time.perf_counter() - started) * 1000
    for r in results:
        title = (r.get("display_headline") or "").splitlines()[0][:70]
        print(f"  {r['date']}  {title}\n    {r.get('paper') or ''}")
        print(
            f"    story place: {r.get('place') or 'not stated'}   score {r['score']:.2f}"
        )
        if r.get("highlights"):
            print(f"    matched: {matched(r)}")
    print(f"{len(results)} found in {ms:.0f} ms")
    sentry_sdk.flush()


if __name__ == "__main__":
    main(sys.argv[1:])
