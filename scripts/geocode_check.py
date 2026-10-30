"""The geocoder's accuracy (decision 34), against answers checked by hand in
eval/results/phase2b/geocoder_expected.json:
1. a seeded 200 of the papers' distinct (place, state) pairs, from the title lookup, each
   geocoded twice: its printed place alone, and checked against its paper's loc.gov title
   record (`paperghosts.geo.papers`), which is asked for once and cached
2. the 24 judged reports' story places, as their text gives them, as an early look at the
   places the reader will extract

A result is right when it is the expected GeoNames ID, or no point where no GeoNames place is
right. A wrong result is a wrong pin or no pin, and its kind is the one the answers record, or
"not foreseen" for one to check by hand. Writes eval/results/phase2b/geocoder.json, with Wilson
intervals. `--review` prints the draw with each result's runners-up instead."""

import json
import random
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from paperghosts.geo import loc
from paperghosts.geo.geonames import Gazetteer, flat, name_key
from paperghosts.geo.papers import modern_state, paper_place, printed_place, towns
from paperghosts.stats import wilson

ROOT = Path(__file__).parents[1]
LOOKUP = ROOT / "data" / "titles" / "titles.json"
RESULTS = ROOT / "eval" / "results" / "phase2b"
EXPECTED = RESULTS / "geocoder_expected.json"
OUT = RESULTS / "geocoder.json"
SEED, PAIRS = "2B geocoder", 200


def order(lccns):
    """The papers in the seeded order the draw walks them."""
    lccns = sorted(lccns)
    random.Random(SEED).shuffle(lccns)
    return lccns


def draw():
    """The first 200 distinct (place, state) pairs of the papers, walked in seeded order."""
    titles = json.loads(LOOKUP.read_text())
    sample, seen = [], set()
    for lccn in order(titles):
        title = titles[lccn]
        tried, state = towns(title), modern_state(title)
        pair = (tried[0] if tried else None, state)
        if pair not in seen:
            seen.add(pair)
            sample.append(
                {
                    "town": pair[0],
                    "state": state,
                    "towns": tried,
                    "county": title.get("county"),
                    "lccn": lccn,
                    "title": title,
                }
            )
        if len(sample) == PAIRS:
            return sample
    raise ValueError("fewer distinct pairs than the draw needs")


def rate(right, n):
    low, high = wilson(right, n)
    return {
        "right": right,
        "n": n,
        "share": right / n if n else None,
        "low": low,
        "high": high,
    }


def judged(found, want):
    """Whether a result is right, and the kind of failure where it isn't."""
    right = found["place_id"] == want["place_id"] and (
        found["place_id"] is not None or want["failure"] is None
    )
    failure = None if right else want["failure"] or "not foreseen: to check by hand"
    return {
        "found": found["place_id"],
        "reason": found.get("reason"),
        "right": right,
        "failure": failure,
    }


def summary(results):
    resolved = [r for r in results if r["found"] is not None]
    return {
        "right": rate(sum(r["right"] for r in results), len(results)),
        "resolved": len(resolved),
        "right_when_resolved": rate(sum(r["right"] for r in resolved), len(resolved)),
        "wrong_pins": sum(not r["right"] for r in resolved),
        "failures": dict(Counter(r["failure"] for r in results if not r["right"])),
    }


def review(gazetteer, sample):
    for n, pair in enumerate(sample, 1):
        found = printed_place(gazetteer, pair["title"])
        code = gazetteer.states.get((pair["state"] or "").lower())
        others = []
        for town in pair["towns"]:
            key = flat(name_key(town))
            for kind, index in (
                ("name", gazetteer.names),
                ("alt", gazetteer.alternates),
            ):
                for p in index.get((key, code), []):
                    county = gazetteer.county_names.get((code, p["county"]))
                    others.append(
                        f"{p['id']} {p['name']} ({county}, {p['code']}, {p['population']}, {kind})"
                    )
        print(
            f"{n:3} {pair['towns']} | {pair['state']} | county {pair['county']} | {pair['lccn']}"
        )
        print(
            f"    -> {found.get('place_id')} {found.get('name')} ({found.get('county')}, {found.get('feature_code')}, {found.get('population')}) {found.get('reason', '')}"
        )
        for other in dict.fromkeys(others):
            if not other.startswith(str(found.get("place_id"))):
                print(f"       also {other}")
        given = loc.recorded(loc.title_record(pair["lccn"]))
        checked = paper_place(gazetteer, pair["title"], given)
        if checked["place_id"] != found["place_id"]:
            print(
                f"    checked: {checked['place_id']} {checked.get('name')} ({checked.get('county')}) {checked['record']}"
            )


def main():
    gazetteer = Gazetteer()
    sample = draw()
    if sys.argv[1:] == ["--review"]:
        review(gazetteer, sample)
        return
    expected = json.loads(EXPECTED.read_text())
    papers, records = [], Counter()
    for pair in sample:
        want = expected["papers"][f"{pair['town']}|{pair['state']}"]
        record = loc.title_record(pair["lccn"])
        given = loc.recorded(record)
        records["found" if given else str(record["status"])] += 1
        checked = paper_place(gazetteer, pair["title"], given)
        papers.append(
            {k: v for k, v in pair.items() if k != "title"}
            | {
                "expected": want["place_id"],
                "catalogued": given
                and [given["place"], given["counties"], given["state"]],
                "without_the_record_check": judged(
                    printed_place(gazetteer, pair["title"]), want
                ),
                "with_the_record_check": judged(checked, want)
                | {"record": checked["record"]},
            }
        )
    stories, hinted = [], Counter()
    for story in expected["stories"]:
        found = gazetteer.geocode(story["town"], story["state"], story.get("county"))
        row = story | {
            "found": found.get("place_id"),
            "reason": found.get("reason"),
            "right": found.get("place_id") == story["place_id"],
        }
        if story["given"] == "town only":
            # what the paper's own state would give, against where the story happened
            guess = gazetteer.geocode(
                story["town"], story["paper_state"], story.get("county")
            )
            row["with_the_papers_state"] = guess.get("place_id")
            hinted[
                "nothing"
                if guess.get("place_id") is None
                else "right"
                if guess["place_id"] == story["true_place_id"]
                else "a wrong place"
            ] += 1
        stories.append(row)
    named = [s for s in stories if s["town"] and s["state"]]
    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "gazetteer": gazetteer.source,
        "papers": {
            "seed": SEED,
            "pairs": len(papers),
            "without_the_record_check": summary(
                [p["without_the_record_check"] for p in papers]
            ),
            "with_the_record_check": summary(
                [p["with_the_record_check"] for p in papers]
            )
            | {
                "record": dict(
                    Counter(p["with_the_record_check"]["record"] for p in papers)
                )
            },
            "title_records": dict(records)
            | {
                "requests": loc.COUNTS["requests"],
                "cache_hits": loc.COUNTS["cache_hits"],
                "errors_not_cached": loc.COUNTS["errors"],
            },
            "results": papers,
        },
        "stories": {
            "reports": len(stories),
            "as_the_text_gives_them": dict(Counter(s["given"] for s in stories)),
            "right_with_town_and_state": rate(
                sum(s["right"] for s in named), len(named)
            ),
            "town_only_with_the_papers_state": dict(hinted),
            "results": stories,
        },
    }
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report["papers"].items() if k != "results"}, indent=1
        )
    )
    print(
        json.dumps(
            {k: v for k, v in report["stories"].items() if k != "results"}, indent=1
        )
    )


if __name__ == "__main__":
    main()
