"""Loads the walking skeleton's article into the scratch collection paperghosts.skeleton.

Run after scripts/phase1_env.py, which saves the 1850 Stratford matches to data/skeleton/.
"""

from pathlib import Path

import orjson
import pymongo

from paperghosts.config import setting
from paperghosts.ingest.crops import crop_urls, page_service
from paperghosts.ingest.headline import display_headline

MATCHES = (
    Path(__file__).resolve().parents[1] / "data" / "skeleton" / "stratford_1850.json"
)
PAPER, DATE = "Lewistown gazette", "1850-07-26"


def main():
    match = next(
        m
        for m in orjson.loads(MATCHES.read_bytes())
        if m["page"]["lccn"]["title"].startswith(PAPER)
        and m["page"]["edition"]["date"] == DATE
    )
    article, page = match["article"], match["page"]
    document = {
        "_id": article["id"],
        "paper": page["lccn"]["title"],
        "date": page["edition"]["date"],
        "headline": article["headline"],
        "display_headline": display_headline(
            article["headline"], page["lccn"]["title"]
        ),
        "text": article["article"],
        "bbox_list": article["bbox_list"],
        "crop_urls": crop_urls(
            page_service(match["member"], page["scan"]), article["bbox_list"]
        ),
    }
    with pymongo.MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        client["paperghosts"]["skeleton"].replace_one(
            {"_id": document["_id"]}, document, upsert=True
        )
    print(f"loaded {document['_id']}")
    for url in document["crop_urls"]:
        print(f"crop {url}")


if __name__ == "__main__":
    main()
