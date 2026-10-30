"""The budget probe's documents: a story is its earliest printing, a scan record's "na" page is
left unset, its parts add up to the whole, and each lever changes only its own part: rule 6's,
turned off, add bytes, and the further ones save them."""

import random

import bson
from budget_probe import BASE, parts, story, variants

RAW = "https://chroniclingamerica.loc.gov/data/batches/dlc_deadnettle_ver01/data/sn83030313/00271743919/1875121601/0981.jp2"


def row(day, text):
    member = f"1875-12-{day}_pna_sn83030313_00271743919_187512{day}01_0981.json"
    return {
        "member": f"faro_1875/{member}",
        "article_id": f"3_{member}",
        "lccn": "sn83030313",
        "paper": "The New York herald.",
        "state": "New York",
        "date": f"1875-12-{day}",
        "scan": {"edition": "ed-01", "page": "na", "raw_data_loc": RAW},
        "bbox_list": [{"x0": 1, "y0": 2, "x1": 30, "y1": 40}],
        "headline": "A GHOST",
        "text": text,
        "terms": {"ghost": ["ghost"]},
    }


def test_a_story_is_its_earliest_printing_and_each_lever_changes_only_its_part():
    rows = [
        row("17", "Later it was told again. " * 9),
        row("16", "The ghost walked in Brooklyn. " * 9),
    ]

    doc, members = story(random.Random(1), rows)
    sizes = {k: len(bson.encode(v)) for k, v in variants(doc, members).items()}

    assert doc["primary_article_id"].startswith("3_1875-12-16")
    assert [p.get("page") for p in doc["printings"]] == [None, None]
    base = sizes.pop(BASE)
    assert all(found > 0 for found in parts(doc).values())  # no part counted twice
    assert sizes.pop("int8 embedding") == base - (1536 - 384)
    for label, found in sizes.items():
        assert (found > base) == label.startswith("rule 6 off"), label
    assert (
        sizes["the three, int8"]
        < sizes["the three, float32"]
        < min(sizes[k] for k in sizes if not k.startswith(("rule 6 off", "the three")))
    )
