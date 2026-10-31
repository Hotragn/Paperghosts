"""The title lookup by LCCN (BUDGET.md's lever, decision 34), for every LCCN among v2's
candidates:
- its title, place and state as printed, from its most complete title string
- or, where no string of it names a place or state, from its loc.gov title record, asked for
  once and cached (`paperghosts.geo.loc`)
- its state today, as most of its candidates' records give it, and the two shown together as
  "Charlestown, Va. (now W.Va.)"
- its place as catalogued today, from any title record already cached, and the record's town
  shown where the record check puts the paper's point there (`paperghosts.geo.papers`): "East
  Saginaw, Mich. (now Saginaw)". A paper that moved keeps its printed town.

Writes data/titles/titles.json. Writes eval/results/phase2b/titles.json with the counts: where
the places came from, and loc.gov's requests and cache hits."""

import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import zstandard

from paperghosts.geo import loc
from paperghosts.geo.geonames import Gazetteer
from paperghosts.geo.papers import paper_place
from paperghosts.geo.titles import parse_title, state_name, then_and_now
from paperghosts.ingest.crops import MEMBER
from paperghosts.schemas import Title

ROOT = Path(__file__).parents[1]
DATA = ROOT / "data"
LOOKUP = DATA / "titles" / "titles.json"
OUT = ROOT / "eval" / "results" / "phase2b" / "titles.json"
PLACE = ("place", "supplied_place", "state", "supplied_state")
# the record check's outcomes that put a paper's point at its record's place, checked
FROM_THE_RECORD = {"replaced the printed place", "found what the printed place didn't"}


def year_titles(path):
    """Each LCCN's title strings, record states and candidates in one year's file."""
    found = {}
    with zstandard.open(path, "rt") as rows:
        for row in map(json.loads, rows):
            lccn = row["lccn"] or MEMBER.search(row["member"])["lccn"]
            entry = found.setdefault(
                lccn, {"papers": Counter(), "states": Counter(), "candidates": 0}
            )
            entry["papers"][row["paper"]] += bool(row["paper"])
            entry["states"][row["state"]] += bool(row["state"])
            entry["candidates"] += 1
    return found


def most_complete(papers):
    """The parse of the title string that says the most: the most place fields, then the
    longest string."""
    parsed = [(parse_title(p), p) for p in papers if p]
    if not parsed:
        return None
    return max(
        parsed,
        key=lambda pair: (sum(bool(pair[0][k]) for k in PLACE), len(pair[1]), pair[1]),
    )[0]


def entry(lccn, papers, states, gazetteer):
    modern = max((s for s in states if s), key=lambda s: (states[s], s), default=None)
    found = most_complete(papers) or parse_title(None)
    found = found | {
        "source": "title string" if any(found[k] for k in PLACE) else "none"
    }
    # a record is asked for only where no string names a place, and used wherever it's cached
    given = None
    if found["source"] == "none" or (loc.CACHE / f"{lccn}.json").exists():
        record = loc.title_record(lccn)
        given = loc.recorded(record)
    if given:
        found |= {
            "catalogued_place": given["place"],
            "catalogued_county": given["county"],
            "catalogued_state": given["state"],
            "record_url": record["url"],
            "retrieved": record["retrieved"],
        }
    if given and found["source"] == "none":
        found |= {
            "source": "loc.gov title record",
            "supplied_place": given["place"],
            "supplied_state": given["state"],
            "county": found["county"] or given["county"],
        }
        if not found["title"] and given["title"]:
            found["title"] = parse_title(given["title"])["title"]
        if not found["years"] and given["years"]:
            found["years"] = given["years"]
        modern = modern or state_name(given["state"])
    found["modern_state"] = modern
    catalogued = None
    if given and paper_place(gazetteer, found, given)["record"] in FROM_THE_RECORD:
        catalogued = given["place"]
    found["then_and_now"] = then_and_now(found, modern, catalogued)
    title = Title.model_validate({"_id": lccn, **found})
    return title.model_dump(by_alias=True, exclude_none=True)


def shown(title, modern=None, catalogued=None):
    return then_and_now({k: title.get(k) for k in PLACE}, modern, catalogued)


def main():
    merged = {}
    with ProcessPoolExecutor(max_workers=6) as pool:
        for found in pool.map(
            year_titles, sorted((DATA / "candidates").glob("*.jsonl.zst"))
        ):
            for lccn, e in found.items():
                m = merged.setdefault(
                    lccn, {"papers": Counter(), "states": Counter(), "candidates": 0}
                )
                m["papers"].update(e["papers"])
                m["states"].update(e["states"])
                m["candidates"] += e["candidates"]
    gazetteer = Gazetteer()
    titles = {
        lccn: entry(lccn, m["papers"], m["states"], gazetteer)
        for lccn, m in sorted(merged.items())
    }
    LOOKUP.parent.mkdir(parents=True, exist_ok=True)
    LOOKUP.write_text(json.dumps(titles, indent=1, ensure_ascii=False) + "\n")

    sources = Counter(t["source"] for t in titles.values())
    candidates = Counter()
    for lccn, t in titles.items():
        candidates[t["source"]] += merged[lccn]["candidates"]
    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "lccns": len(titles),
        "places_from": dict(sources),
        "candidates_by_source": dict(candidates),
        "printed_state_differs_from_modern": sum(
            shown(t) != shown(t, t.get("modern_state")) for t in titles.values()
        ),
        # renamed, merged or moved: the record names another town than the printed one
        "catalogued_under_another_town": sum(
            shown(t) != shown(t, None, t.get("catalogued_place"))
            for t in titles.values()
        ),
        "shown_with_the_records_town": sum(
            t.get("then_and_now") != shown(t, t.get("modern_state"))
            for t in titles.values()
        ),
        "records_used": sum("catalogued_place" in t for t in titles.values()),
        "no_modern_state": sum("modern_state" not in t for t in titles.values()),
        "loc_gov": {
            "requests": loc.COUNTS["requests"],
            "cache_hits": loc.COUNTS["cache_hits"],
            "errors_not_cached": loc.COUNTS["errors"],
            "records_cached": len(list(loc.CACHE.glob("*.json"))),
            "not_found": sum(
                json.loads(p.read_text())["status"] == 404
                for p in loc.CACHE.glob("*.json")
            ),
        },
    }
    OUT.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
