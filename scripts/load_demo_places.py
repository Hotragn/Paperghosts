"""Near this town, for the Morgue: the towns its 78 reports' papers were printed in, geocoded from
the GeoNames dumps in data/geonames (a lookup, no model), upserted into paperghosts.places with
their report counts and years, and found with $geoNear on the places collection's 2dsphere index.
Every place here is where a paper was printed, never where a story happened.

  uv run python scripts/load_demo_places.py load             geocode and upsert; never deletes
  uv run python scripts/load_demo_places.py near TOWN STATE [KM]   printed-in towns within KM
                                                                   (default 300) of a town
Writes eval/results/atlas_places.json.
"""

import json
import subprocess
import sys
import time
from collections import defaultdict

from label_gold import ROOT
from pymongo import MongoClient

from paperghosts.config import setting
from paperghosts.geo.geonames import Gazetteer
from paperghosts.schemas import Place
from paperghosts.store.db_init import DATABASE

DEMO = ROOT / "web" / "public" / "reports.json"
RESULT = ROOT / "eval" / "results" / "atlas_places.json"
KIND = "printed in: where the papers were printed, not where the stories happened"


def towns(reports: list) -> dict:
    found = defaultdict(list)
    for r in reports:
        where = r["printed_in"]
        if where["place"] and where["state"]:
            found[(where["place"], where["state"])].append(r)
    return found


def load() -> None:
    reports = json.loads(DEMO.read_text())
    started = time.time()
    gazetteer = Gazetteer()
    loaded = time.time() - started
    code = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    docs, missed = {}, []
    for (town, state), printed in towns(reports).items():
        hit = gazetteer.geocode(town, state)
        if hit["place_id"] is None:
            missed.append({"town": town, "state": state, "reason": hit.get("reason")})
            continue
        years = [int(r["date"][:4]) for r in printed]
        doc = docs.setdefault(hit["place_id"], {"years": [], "hit": hit})
        doc["years"] += years
    places = [
        Place.model_validate(
            {
                "_id": pid,
                "name": d["hit"]["name"],
                "state": d["hit"]["state"],
                "location": d["hit"]["location"],
                "report_count": len(d["years"]),
                "first_year": min(d["years"]),
                "last_year": max(d["years"]),
                "versions": {"code": code, "model": KIND},
            }
        ).model_dump(by_alias=True, exclude_none=True)
        for pid, d in docs.items()
    ]
    with MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        collection = client[DATABASE]["places"]
        changed = [
            collection.replace_one({"_id": p["_id"]}, p, upsert=True) for p in places
        ]
        stats = client[DATABASE].command("collStats", "places")
        found = {
            "kind": KIND,
            "printed_in_towns": len(towns(reports)),
            "geocoded": len(places),
            "missed": missed,
            "reports_covered": sum(p["report_count"] for p in places),
            "inserted": sum(c.upserted_id is not None for c in changed),
            "places_in_collection": collection.count_documents({}),
            "storage_kb": round(stats["storageSize"] / 1024, 1),
            "gazetteer_load_seconds": round(loaded, 1),
            "source": gazetteer.source,
        }
    RESULT.write_text(json.dumps(found, indent=1) + "\n")
    print(json.dumps(found, indent=1))


def near(town: str, state: str, km: float = 300) -> None:
    gazetteer = Gazetteer()
    hit = gazetteer.geocode(town, state)
    if hit["place_id"] is None:
        sys.exit(f"{town}, {state} isn't in GeoNames: {hit.get('reason')}")
    reports = json.loads(DEMO.read_text())
    with MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        collection = client[DATABASE]["places"]
        pipeline = [
            {
                "$geoNear": {
                    "near": hit["location"],
                    "distanceField": "metres",
                    "maxDistance": km * 1000,
                    "spherical": True,
                }
            },
            {
                "$project": {
                    "name": 1,
                    "state": 1,
                    "report_count": 1,
                    "first_year": 1,
                    "last_year": 1,
                    "metres": 1,
                }
            },
        ]
        started = time.perf_counter()
        found = list(collection.aggregate(pipeline))
        ms = (time.perf_counter() - started) * 1000
    print(
        f"papers printed within {km:g} km of {hit['name']}, {hit['state']} (the papers' towns, not the stories'):"
    )
    # each printed-in town's reports, by its GeoNames ID, so two towns of one name never mix
    by_place = defaultdict(list)
    for (t, st), printed in towns(reports).items():
        by_place[gazetteer.geocode(t, st)["place_id"]] += printed
    for p in found:
        print(
            f"  {p['name']}, {p['state']}  {p['metres'] / 1000:.0f} km  {p['report_count']} report(s), {p['first_year']}–{p['last_year']}"
        )
        for r in by_place[p["_id"]]:
            print(f"      {r['date']}  {(r['headline'].splitlines() or [''])[0][:60]}")
    print(f"{len(found)} towns in {ms:.0f} ms")


if __name__ == "__main__":
    mode, *rest = sys.argv[1:]
    load() if mode == "load" else near(rest[0], rest[1], *map(float, rest[2:]))
