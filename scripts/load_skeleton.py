"""Loads the walking skeleton's article into the scratch collection paperghosts.skeleton.

Run after scripts/phase1_env.py, which saves the 1850 Stratford matches to data/skeleton/.
"""

import re
from pathlib import Path

import httpx
import orjson
import pymongo

from paperghosts.config import setting
from paperghosts.ingest.crops import crop_url, service_id

MATCHES = (
    Path(__file__).resolve().parents[1] / "data" / "skeleton" / "stratford_1850.json"
)
PAPER, DATE = "Lewistown gazette", "1850-07-26"


def page_service(match):
    raw_data_loc = match["page"]["scan"].get("raw_data_loc")
    if raw_data_loc:
        return service_id(raw_data_loc)
    # some scans have no raw_data_loc, so ask loc.gov which batch holds the page
    name = match["member"].rsplit("/", 1)[-1].removesuffix(".json")
    date, _, lccn, reel, issue, seq = name.split("_")
    item = f"https://www.loc.gov/item/{lccn}/{date}/ed-{int(issue[-2:])}/"
    listing = httpx.get(
        item, params={"fo": "json"}, timeout=30, follow_redirects=True
    ).text
    found = re.search(
        rf"service:ndnp:[a-z]+:batch_\w+?:data:{lccn}:{reel}:{issue}:{seq}", listing
    )
    if found is None:
        raise SystemExit(f"loc.gov lists no IIIF service for {name}")
    return found[0]


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
        "text": article["article"],
        "bbox_list": article["bbox_list"],
        "crop_url": crop_url(page_service(match), article["bbox_list"]),
    }
    with pymongo.MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        client["paperghosts"]["skeleton"].replace_one(
            {"_id": document["_id"]}, document, upsert=True
        )
    print(f"loaded {document['_id']}")
    print(f"crop {document['crop_url']}")


if __name__ == "__main__":
    main()
