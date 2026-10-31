"""The storage budget's measurements (decision 32, rule 8): full `reports` documents, with their
real text, their reprint clusters' printings, a BinData embedding, and reader fields whose quotes
are real sentences of the article. They are built for a seeded 1,000 of lexicon v2's candidates,
and for the judged reports that v2 makes candidates.

1. Offline, with bson.encode: the bytes of each document by part, with each of rule 6's levers
   turned off, and with each further lever on: bbox_list packed as BinData, paper, place and
   state in a title lookup by LCCN, display_headline derived at read time, and an int8 embedding.
2. Atlas's own data and index sizes, for the 1,000 loaded 500 at a time into a scratch
   collection with the reports validator and indexes. The collection is dropped afterwards.
3. Each database's use of M0's storage: data size plus index size, as Atlas counts it.
4. How many stories fit at the top of decisions 30 and 31's intervals.

Writes eval/results/phase2b/budget.json, which Docs/BUDGET.md reads."""

import json
import random
import re
import statistics
import time
import uuid
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import bson
import numpy as np
import zstandard
from bson.binary import Binary, BinaryVectorDtype
from pymongo import MongoClient

from paperghosts.cluster.reprints import clusters, keys
from paperghosts.config import setting
from paperghosts.ingest.crops import MEMBER, crop_urls
from paperghosts.ingest.headline import display_headline
from paperghosts.schemas import DIMENSIONS, Report
from paperghosts.store.db_init import INDEXES
from paperghosts.store.printings import printing
from paperghosts.store.validators import validator

ROOT = Path(__file__).parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "eval" / "results"
OUT = RESULTS / "phase2b" / "budget.json"
SEED, PICKS, BATCH = "2B budget probe", 1_000, 500
SETTLE = 75  # seconds: WiredTiger's checkpoint, once a minute, updates the index sizes
CODE = "0123456789abcdef0123456789abcdef01234567"  # a git SHA's length
OUTCOMES = ["unexplained", "explained", "hoax", "unknown"]
PLACE_TYPES = ["house", "church", "cemetery", "road_or_bridge", "other"]
BOX = ("x0", "y0", "x1", "y1")
BASE = "as stored: rule 6's levers on, float32"
LIMIT = 500_000_000  # M0's "0.5 GB"; read as 512 MiB it would be 536,870,912
PRINTINGS = 74_027 + 21_176  # the tops of decision 27's and decision 31's intervals
STORIES_PER_PRINTING = 22_300 / 36_766  # lexicon v1's (decision 27)


def year_keys(year):
    """Each candidate's reprint keys and article ID in file order, and each LCCN's title."""
    found, ids, titles = [], [], {}
    with zstandard.open(DATA / "candidates" / f"{year}.jsonl.zst", "rt") as rows:
        for row in map(json.loads, rows):
            found.append(tuple(keys(row["text"])))
            ids.append(row["article_id"])
            lccn = row["lccn"] or MEMBER.search(row["member"])["lccn"]
            titles.setdefault(lccn, {"paper": row["paper"], "state": row["state"]})
    return year, found, ids, titles


def year_rows(job):
    year, wanted = job
    found = {}
    with zstandard.open(DATA / "candidates" / f"{year}.jsonl.zst", "rt") as rows:
        for index, row in enumerate(rows):
            if index in wanted:
                found[index] = json.loads(row)
    return year, found


def sentences(text):
    flat = " ".join((text or "").replace("-\n", "").split())
    return [s for s in re.split(r"(?<=[.!?])\s+", flat) if len(s) >= 30] or [flat[:200]]


def quote(sentence, most=200):
    """A verbatim span, as the reader quotes one: a sentence, cut at a word under `most`."""
    return sentence if len(sentence) <= most else sentence[:most].rsplit(" ", 1)[0]


def stated(rng, said, value=None):
    sentence = rng.choice(said)
    if value is None:
        words = sentence.split()
        start = rng.randrange(max(1, len(words) - 6))
        value = " ".join(words[start : start + rng.randint(3, 6)])
    return {
        "value": value,
        "quote": quote(sentence),
        "verified": True,
        "score": round(rng.random(), 3),
    }


def name(rng, said, words):
    """A run of capitalized words from the text, as a place or a person reads."""
    runs = re.findall(
        rf"\b[A-Z][a-z]{{2,}}(?: [A-Z][a-z]{{2,}}){{{words - 1}}}\b", " ".join(said)
    )
    return rng.choice(runs) if runs else rng.choice(" ".join(said).split()[:8] or ["?"])


def story(rng, members):
    """A full reports document for one cluster's printings, primary first: the earliest."""
    members = sorted(members, key=lambda row: (row["date"], row["article_id"]))
    primary = members[0]
    said = sentences(primary["text"])
    town = name(rng, said, 1)
    people = [
        stated(rng, said, name(rng, said, 2))
        for _ in range(rng.choice([0, 0, 1, 1, 2, 3]))
    ]
    vector = np.random.default_rng(rng.randrange(2**32)).normal(size=DIMENSIONS)
    year = int(primary["date"][:4])
    doc = {
        "_id": f"r_{primary['article_id']}",
        "primary_article_id": primary["article_id"],
        "printings": [printing(row) for row in members],
        "headline": primary["headline"] or "",
        "text": primary["text"] or "",
        "display_headline": display_headline(
            primary["headline"] or "", primary["paper"], primary["date"]
        ),
        "date": primary["date"],
        "year": year,
        "month_day": primary["date"][5:],
        "decade": year // 10 * 10,
        "kind": "report",
        "fields": {
            "place": stated(rng, said, town),
            "people": people,
            "seen": stated(rng, said),
            "outcome": stated(rng, said, rng.choice(OUTCOMES)),
            "specific_place": stated(rng, said),
            "place_type": stated(rng, said, rng.choice(PLACE_TYPES)),
            "precision": stated(rng, said, "town"),
        },
        "location": {
            "type": "Point",
            "coordinates": [
                round(rng.uniform(-124, -67), 6),
                round(rng.uniform(25, 49), 6),
            ],
        },
        "location_precision": "town",
        "location_source": f"geonames:{rng.randrange(4_000_000, 6_000_000)}",
        "place_id": rng.randrange(4_000_000, 6_000_000),
        "town": town,
        "state": primary["state"],
        "embedding": Binary.from_vector(vector.tolist(), BinaryVectorDtype.FLOAT32),
        "versions": {
            "code": CODE,
            "lexicon": "v2",
            "model": "Qwen/Qwen3.5-4B",
            "adapter": "paperghosts-reader-lora-v1",
            "prompt": "reader-v1",
        },
        "lexicon_terms": sorted(primary["terms"]),
    }
    stored = Report.model_validate(doc).model_dump(by_alias=True, exclude_none=True)
    return stored, members


def int8(values):
    v = np.asarray(values)
    scaled = np.round(v * (127 / np.abs(v).max())).astype(np.int8)
    return Binary.from_vector(scaled.tolist(), BinaryVectorDtype.INT8)


def packed(boxes, dtype):
    """bbox_list as BinData: each box's x0, y0, x1, y1, little-endian, unpacked when read."""
    return Binary(
        np.array([[box[k] for k in BOX] for box in boxes], dtype=dtype).tobytes()
    )


def variants(doc, members):
    """The document as stored, with each of rule 6's levers turned off, and with each further
    lever on, alone and together."""
    texts = {row["article_id"]: row["text"] or "" for row in members}
    floats = doc["embedding"].as_vector().data

    def crops(p):
        service = p.get("service")
        if service is None:  # its service would be looked up: one of the usual length
            where = f"{p['lccn']}:{p['reel']}:{p['issue']}:{p['frame']}"
            service = f"service:ndnp:xx:batch_xx_unknown_ver01:data:{where}"
        return crop_urls(service, p["bbox_list"])

    def each(change):
        return [change(dict(p)) for p in doc["printings"]]

    untitled = each(
        lambda p: {k: v for k, v in p.items() if k not in ("paper", "place", "state")}
    )
    bare = {k: v for k, v in doc.items() if k != "display_headline"}
    three = bare | {
        "printings": [
            p | {"bbox_list": packed(p["bbox_list"], "<i2")} for p in untitled
        ]
    }
    return {
        BASE: doc,
        "rule 6 off: embedding as an array of doubles": doc
        | {"embedding": list(floats)},
        "rule 6 off: crop URLs stored": doc
        | {"printings": each(lambda p: p | {"crop_urls": crops(p)})},
        "rule 6 off: printings with their own text": doc
        | {"printings": each(lambda p: p | {"text": texts[p["article_id"]]})},
        "bbox_list as int16 BinData": doc
        | {
            "printings": each(
                lambda p: p | {"bbox_list": packed(p["bbox_list"], "<i2")}
            )
        },
        "bbox_list as int32 BinData": doc
        | {
            "printings": each(
                lambda p: p | {"bbox_list": packed(p["bbox_list"], "<i4")}
            )
        },
        "paper, place and state in a title lookup": doc | {"printings": untitled},
        "display_headline derived at read time": bare,
        "int8 embedding": doc | {"embedding": int8(floats)},
        "the three, float32": three,
        "the three, int8": three | {"embedding": int8(floats)},
    }


def parts(doc):
    """The document's bytes by part; the rest is its ids, dates, place, versions and terms."""

    def element(key, value):
        return len(bson.encode({key: value})) - len(bson.encode({}))

    boxes = sum(element("bbox_list", p["bbox_list"]) for p in doc["printings"])
    found = {
        "text": element("text", doc["text"]),
        "headline and display headline": element("headline", doc["headline"])
        + element("display_headline", doc["display_headline"]),
        "printings, apart from their boxes": element("printings", doc["printings"])
        - boxes,
        "printings' bbox_list": boxes,
        "reader fields": element("fields", doc["fields"]),
        "embedding": element("embedding", doc["embedding"]),
    }
    found["the rest"] = len(bson.encode(doc)) - sum(found.values())
    return found


def summary(sizes):
    ordered = sorted(sizes)
    return {
        "total": sum(ordered),
        "mean": round(statistics.fmean(ordered), 1),
        "median": statistics.median(ordered),
        "p90": ordered[int(0.9 * (len(ordered) - 1))],
        "max": ordered[-1],
    }


def measure(built):
    """Bytes by part and by variant for a list of (doc, members), and a story's bytes as the
    story itself and so much per printing."""
    by_part, by_variant = defaultdict(list), defaultdict(list)
    alone, extra, printings = defaultdict(list), defaultdict(int), []
    for doc, members in built:
        printings.append(len(doc["printings"]))
        for label, value in parts(doc).items():
            by_part[label].append(value)
        for label, variant in variants(doc, members).items():
            whole = len(bson.encode(variant))
            bare = len(bson.encode(variant | {"printings": []}))
            by_variant[label].append(whole)
            alone[label].append(bare)
            extra[label] += whole - bare
    return {
        "stories": len(built),
        "printings": {
            "total": sum(printings),
            "per_story": round(sum(printings) / len(printings), 2),
            "stories_with_more_than_one": sum(n > 1 for n in printings),
            "most": max(printings),
        },
        "bytes_by_part": {label: summary(v) for label, v in by_part.items()},
        "bytes": {label: summary(v) for label, v in by_variant.items()},
        "bytes_per": {
            label: {
                "story_without_its_printings": round(statistics.fmean(alone[label]), 1),
                "printing": round(extra[label] / sum(printings), 1),
            }
            for label in by_variant
        },
    }


def settled(collection):
    time.sleep(SETTLE)
    stats = next(collection.aggregate([{"$collStats": {"storageStats": {}}}]))
    stats = stats["storageStats"]
    return {
        "count": stats["count"],
        "data_bytes": stats["size"],
        "storage_bytes": stats["storageSize"],
        "index_bytes": stats["totalIndexSize"],
        "index_bytes_by_index": stats["indexSizes"],
    }


def atlas(docs):
    """The 1,000 in a scratch collection with the reports validator and its indexes (no
    Search indexes: M0's cap), 500 at a time, then the collection dropped."""
    with MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        db = client["paperghosts"]
        scratch = db.create_collection(
            f"scratch_budget_{uuid.uuid4().hex[:8]}", validator=validator(Report)
        )
        try:
            scratch.create_indexes(INDEXES["reports"])
            steps = {"empty": settled(scratch)}
            for start in range(0, len(docs), BATCH):
                scratch.insert_many(docs[start : start + BATCH], ordered=False)
                steps[f"after {min(start + BATCH, len(docs))}"] = settled(scratch)
        finally:
            scratch.drop()
        left = scratch.name in db.list_collection_names()
        storage = {
            name: {k: s[k] for k in ("dataSize", "indexSize", "storageSize")}
            | {"counted": s["dataSize"] + s["indexSize"]}
            for name in client.list_database_names()
            if name not in ("admin", "local")
            for s in [client[name].command("dbStats")]
        }
    return steps, left, storage


def capacity(samples, index_per_story, titles_bytes, storage):
    """Whether the top of the range fits, and how many stories would, per variant: a story's
    bytes from whichever sample has more, its index bytes from Atlas, and the title lookup
    where a variant uses it."""
    counted = {name: s["counted"] for name, s in storage.items()}
    free = {
        "with sample_mflix": LIMIT - sum(counted.values()),
        "without sample_mflix": LIMIT
        - sum(v for k, v in counted.items() if k != "sample_mflix"),
    }
    scenarios = {
        "v1's ratio of stories to printings": round(PRINTINGS * STORIES_PER_PRINTING),
        "one story per printing": PRINTINGS,
    }
    out = {"limit": LIMIT, "printings": PRINTINGS, "free": free, "variants": {}}
    for label in samples[0]["bytes_per"]:
        story_bytes = max(
            s["bytes_per"][label]["story_without_its_printings"] for s in samples
        )
        printing_bytes = max(s["bytes_per"][label]["printing"] for s in samples)
        fixed = (
            titles_bytes
            if "title lookup" in label or label.startswith("the three")
            else 0
        )
        rows = {}
        for scenario, stories in scenarios.items():
            need = (
                stories * (story_bytes + index_per_story)
                + PRINTINGS * printing_bytes
                + fixed
            )
            per = story_bytes + index_per_story + PRINTINGS / stories * printing_bytes
            rows[scenario] = {
                "stories": stories,
                "bytes": round(need),
                "fits": {k: need <= v for k, v in free.items()},
                "stories_that_fit": {
                    k: int((v - fixed) // per) for k, v in free.items()
                },
            }
        out["variants"][label] = {
            "story_bytes": story_bytes,
            "printing_bytes": printing_bytes,
            "fixed_bytes": fixed,
            "scenarios": rows,
        }
    return out


def judged_reports():
    """The 25 reports judged so far: eval A's 7, the screen's 4 and 2A.8's 14."""
    composition = json.loads((RESULTS / "eval_a" / "composition.json").read_text())
    screen = json.loads((RESULTS / "eval_a" / "screen.json").read_text())
    added = json.loads((RESULTS / "eval_a_v2" / "added.json").read_text())
    return {
        "eval A": [
            i["article_id"] for i in composition if i["category"] == "ghost_report"
        ],
        "screen": [i["article_id"] for i in screen if i["ghost_report"]],
        "2A.8": [i["article_id"] for i in added if i["ghost_report"]],
    }


def main():
    counts = {
        c["year"]: c["candidates"]
        for c in (json.loads(p.read_text()) for p in (DATA / "counts").glob("*.json"))
    }
    years = sorted(y for y in counts if counts[y])
    starts, total = {}, 0
    for year in years:
        starts[year], total = total, total + counts[year]
    rng = random.Random(SEED)
    picks = sorted(rng.sample(range(total), PICKS))

    doc_keys, ids, titles = [], [], {}
    with ProcessPoolExecutor(max_workers=6) as pool:
        for _, found, named, held in pool.map(year_keys, years):
            doc_keys += found
            ids += named
            for lccn, title in held.items():
                titles.setdefault(lccn, title)
    assert len(doc_keys) == total
    group_of = {}
    for group in clusters(doc_keys, least=2):
        for doc in group:
            group_of[doc] = group
    del doc_keys
    index_of = {article: i for i, article in enumerate(ids)}
    judged = judged_reports()
    not_candidates = sorted(
        a for found in judged.values() for a in found if a not in index_of
    )

    def groups_of(docs):
        found, seen = [], set()
        for doc in docs:
            group = tuple(group_of.get(doc, (doc,)))
            if group not in seen:  # two picks from one cluster are one story
                seen.add(group)
                found.append(group)
        return found

    sampled = groups_of(picks)
    reports = groups_of(
        sorted(
            {index_of[a] for found in judged.values() for a in found if a in index_of}
        )
    )
    wanted = defaultdict(set)
    for group in sampled + reports:
        for doc in group:
            year = max(y for y in years if starts[y] <= doc)
            wanted[year].add(doc - starts[year])
    with ProcessPoolExecutor(max_workers=6) as pool:
        rows = {
            starts[year] + index: row
            for year, found in pool.map(year_rows, wanted.items())
            for index, row in found.items()
        }
    built = [story(rng, [rows[d] for d in group]) for group in sampled]
    judged_built = [story(rng, [rows[d] for d in group]) for group in reports]
    boxes = [
        v
        for doc, _ in built + judged_built
        for p in doc["printings"]
        for b in p["bbox_list"]
        for v in b.values()
    ]
    title_entries = [
        len(bson.encode({"_id": lccn} | {k: v for k, v in t.items() if v}))
        for lccn, t in titles.items()
    ]

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": SEED,
        "candidates_drawn": PICKS,
        "of_candidates": total,
        "sample": measure(built),
        "judged_reports": {
            "counts": {k: len(v) for k, v in judged.items()},
            "not_v2_candidates": not_candidates,
            **measure(judged_built),
        },
        "largest_box_coordinate": max(boxes),
        "title_lookup": {
            "lccns": len(titles),
            "bytes": sum(title_entries),
            "mean_entry_bytes": round(statistics.fmean(title_entries), 1),
        },
    }
    steps, left, storage = atlas([doc for doc, _ in built])
    first, last = steps[f"after {BATCH}"], steps[f"after {len(built)}"]
    index_per_story = max(
        last["index_bytes"] / last["count"],
        (last["index_bytes"] - first["index_bytes"]) / (last["count"] - first["count"]),
    )
    report["atlas"] = {
        "steps": steps,
        "data_bytes_per_story": last["data_bytes"] / last["count"],
        "index_bytes_per_story": round(index_per_story, 1),
        "scratch_collection_left": left,
    }
    report["storage_by_database"] = storage
    report["capacity"] = capacity(
        [report["sample"], report["judged_reports"]],
        index_per_story,
        report["title_lookup"]["bytes"],
        storage,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1) + "\n")
    for name in ("sample", "judged_reports"):
        s = report[name]
        print(
            f"{name}: {s['stories']} stories, {s['printings']['total']} printings; "
            f"BSON mean {s['bytes'][BASE]['mean']:,} bytes"
        )
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
