"""The stored records' models, and the Atlas validators generated from them: a valid and an
invalid document per collection, and the validator rejecting what the model rejects on required
fields, enums and GeoJSON. Offline, a small $jsonSchema checker stands in for Atlas; the test
marked atlas asks Atlas itself, and is skipped without MONGODB_URI, as in CI."""

import copy
import re
import uuid

import bson
import pytest
from bson.binary import Binary, BinaryVectorDtype
from pydantic import ValidationError
from pymongo import MongoClient
from pymongo.errors import WriteError

from paperghosts.config import setting
from paperghosts.schemas import Case, Place, Report, Stat
from paperghosts.store.validators import validator

ARTICLE = "3_1875-12-16_p6_sn83030313_00271743919_1875121601_0981.json"
SERVICE = "service:ndnp:dlc:batch_dlc_deadnettle_ver01:data:sn83030313:00271743919:1875121601:0981"
VERSIONS = {"code": "2d6ff0faaf81", "lexicon": "v2", "prompt": "reader-1"}


def printing():
    return {
        "article_id": ARTICLE,
        "lccn": "sn83030313",
        "paper": "The New York herald.",
        "state": "New York",
        "date": "1875-12-16",
        "edition": 1,
        "page": 6,
        "service": SERVICE,
        "bbox_list": [{"x0": 2118, "y0": 301, "x1": 3037, "y1": 1990}],
    }


def stated(value):
    return {"value": value, "quote": f"saw {value}", "verified": True, "score": 0.9}


def report():
    return {
        "_id": f"r_{ARTICLE}",
        "primary_article_id": ARTICLE,
        "printings": [printing()],
        "headline": "A GHOST IN BROOKLYN",
        "text": "The neighbours saw a white figure at the window of the empty house.",
        "display_headline": "A GHOST IN BROOKLYN",
        "date": "1875-12-16",
        "year": 1875,
        "month_day": "12-16",
        "decade": 1870,
        "kind": "report",
        "fields": {
            "place": stated("Brooklyn"),
            "people": [stated("Mrs. Smith")],
            "seen": stated("a white figure"),
            "outcome": stated("unexplained"),
            "place_type": stated("house"),
            # not stated: the verifier found no quote for it
            "precision": {"verified": False, "score": 0.2},
        },
        "location": {"type": "Point", "coordinates": [-73.94, 40.65]},
        "location_precision": "town",
        "location_source": "geonames:5110302",
        "place_id": 5110302,
        "town": "Brooklyn",
        "state": "New York",
        "embedding": Binary.from_vector([0.5] * 384, BinaryVectorDtype.FLOAT32),
        "versions": VERSIONS | {"model": "Qwen/Qwen3.5-4B", "adapter": "reader-lora-1"},
        "lexicon_terms": ["phantom"],
    }


def place():
    return {
        "_id": 5110302,
        "name": "Brooklyn",
        "alternate_names": ["Breuckelen"],
        "state": "New York",
        "location": {"type": "Point", "coordinates": [-73.94, 40.65]},
        "report_count": 3,
        "first_year": 1850,
        "last_year": 1910,
        "versions": {"code": "2d6ff0faaf81"},
    }


def case():
    return {
        "_id": f"c_r_{ARTICLE}",
        "report_id": f"r_{ARTICLE}",
        "claims": [
            {
                "text": "The house stood empty after the death of its owner.",
                "clippings": [
                    {
                        "article_id": ARTICLE,
                        "quote": "the empty house",
                        "verified": True,
                    }
                ],
                "confidence": 0.8,
            }
        ],
        "followups": [printing() | {"relation": "debunking", "quote": "it was a cat"}],
        "person": {
            "name": "John Smith",
            "death_notice_article_id": ARTICLE,
            "link_grade": "possible",
            "reasons": ["name match", "date gap of 2 years"],
        },
        "then_now": {
            "then": "An empty house on Fulton Street.",
            "now": [
                {
                    "source": "Wikipedia",
                    "url": "https://en.wikipedia.org/wiki/Fulton_Street_(Brooklyn)",
                    "retrieved": "2026-10-30",
                    "quote": "Fulton Street is a street in Brooklyn",
                }
            ],
            "differences": [
                {
                    "text": "The house is gone.",
                    "then_quote": "the empty house",
                    "now_quote": "a parking garage",
                }
            ],
        },
        "run": {
            "model": "claude-opus-5-5",
            "provider": "anthropic",
            "steps": 12,
            "tokens": 48_000,
            "cost_usd": 1.2,
            "latency_s": 95.0,
            "sentry_trace_id": "0af7651916cd43dd8448eb211c80319c",
            "workflow_id": f"investigate-c_r_{ARTICLE}",
        },
        "versions": {"code": "2d6ff0faaf81", "prompt": "investigator-1"},
    }


def stat():
    return {
        "_id": "year:1875",
        "scope": "year",
        "year": 1875,
        "pages": 90_000,
        "articles": 2_000_000,
        "candidates": 6_000,
        "stories": 120,
        "printings": 200,
        "reports_per_million": 100.0,
        "outcomes": {"unexplained": 80, "explained": 20, "hoax": 15, "unknown": 5},
        "versions": {"code": "2d6ff0faaf81", "lexicon": "v2"},
    }


def change(doc, path, value=None, drop=False):
    """A copy of doc with the value at path (keys and list indexes) replaced, or dropped."""
    doc = copy.deepcopy(doc)
    *parents, last = path
    target = doc
    for key in parents:
        target = target[key]
    if drop:
        del target[last]
    else:
        target[last] = value
    return doc


# what the model rejects, and so must Atlas: required fields, enums, GeoJSON, and rule 6
INVALID = {
    Report: {
        "no text": change(report(), ["text"], drop=True),
        "no printings": change(report(), ["printings"], []),
        "outcome not in its enum": change(
            report(), ["fields", "outcome", "value"], "maybe"
        ),
        "place type not in its enum": change(
            report(), ["fields", "place_type", "value"], "barn"
        ),
        "kind other than report": change(report(), ["kind"], "fiction"),
        "unknown lexicon term": change(report(), ["lexicon_terms"], ["ghosts"]),
        "GeoJSON type not Point": change(report(), ["location", "type"], "Polygon"),
        "latitude past 90": change(
            report(), ["location", "coordinates"], [-73.94, 140.65]
        ),
        "three coordinates": change(
            report(), ["location", "coordinates"], [1.0, 2.0, 3.0]
        ),
        "embedding as an array of doubles": change(
            report(), ["embedding"], [0.5] * 384
        ),
        "crop URLs stored": change(
            report(), ["printings", 0, "crop_urls"], ["https://x"]
        ),
        "month_day not MM-DD": change(report(), ["month_day"], "Dec 16"),
    },
    Place: {
        "no name": change(place(), ["name"], drop=True),
        "longitude past 180": change(
            place(), ["location", "coordinates"], [-273.9, 40.6]
        ),
        "no coordinates": change(place(), ["location", "coordinates"], drop=True),
        "negative report count": change(place(), ["report_count"], -1),
    },
    Case: {
        "no run": change(case(), ["run"], drop=True),
        "relation not in its enum": change(
            case(), ["followups", 0, "relation"], "rumour"
        ),
        "link grade not in its enum": change(
            case(), ["person", "link_grade"], "certain"
        ),
        "claim with no clipping": change(case(), ["claims", 0, "clippings"], []),
    },
    Stat: {
        "no articles": change(stat(), ["articles"], drop=True),
        "scope not in its enum": change(stat(), ["scope"], "decade"),
        "outcome count missing": change(stat(), ["outcomes", "hoax"], drop=True),
    },
}
VALID = {Report: report, Place: place, Case: case, Stat: stat}

BSON_TYPES = {
    "string": lambda v: isinstance(v, str),
    "int": lambda v: type(v) is int and -(2**31) <= v < 2**31,
    "long": lambda v: type(v) is int,
    "number": lambda v: type(v) in (int, float),
    "bool": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list | tuple),
    "null": lambda v: v is None,
    "binData": lambda v: isinstance(v, bytes),
}
KEYWORDS = {
    "bsonType", "enum", "anyOf", "required", "properties", "additionalProperties", "items",
    "additionalItems", "minItems", "maxItems", "minLength", "maxLength", "pattern", "minimum",
    "maximum", "multipleOf",
}  # fmt: skip


def conforms(value, schema):
    """Whether value passes schema, for the $jsonSchema keywords in KEYWORDS."""
    types = schema.get("bsonType", [])
    types = [types] if isinstance(types, str) else types
    if types and not any(BSON_TYPES[t](value) for t in types):
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if "anyOf" in schema and not any(conforms(value, s) for s in schema["anyOf"]):
        return False
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", [])):
            return False
        if schema.get("additionalProperties") is False and set(value) - set(props):
            return False
        if not all(conforms(v, props[k]) for k, v in value.items() if k in props):
            return False
    if isinstance(value, list | tuple):
        if (
            not schema.get("minItems", 0)
            <= len(value)
            <= schema.get("maxItems", len(value))
        ):
            return False
        items = schema.get("items", {})
        if isinstance(items, list):
            if schema.get("additionalItems") is False and len(value) > len(items):
                return False
            pairs = zip(value, items, strict=False)
        else:
            pairs = ((v, items) for v in value)
        if not all(conforms(v, s) for v, s in pairs):
            return False
    if isinstance(value, str):
        if (
            not schema.get("minLength", 0)
            <= len(value)
            <= schema.get("maxLength", len(value))
        ):
            return False
        if "pattern" in schema and not re.search(schema["pattern"], value):
            return False
    if type(value) in (int, float):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            return False
        if "multipleOf" in schema and value % schema["multipleOf"]:
            return False
    return True


def keywords(schema):
    found = set()
    if isinstance(schema, dict):
        for key, value in schema.items():
            found.add(key)
            if key == "properties":
                value = list(value.values())
            found |= keywords(value)
    elif isinstance(schema, list):
        for item in schema:
            found |= keywords(item)
    return found


def stored(model, doc):
    """The document as the model writes it and Atlas gives it back."""
    dumped = model.model_validate(doc).model_dump(by_alias=True, exclude_none=True)
    return bson.decode(bson.encode(dumped))


@pytest.mark.parametrize("model", VALID)
def test_a_valid_document_is_stored_as_given(model):
    doc = VALID[model]()

    assert stored(model, doc) == doc
    assert conforms(doc, validator(model)["$jsonSchema"])


@pytest.mark.parametrize("model", VALID)
def test_the_validator_uses_only_keywords_atlas_supports(model):
    schema = validator(model)["$jsonSchema"]

    # no $ref, $defs, const, type, format, title or default, which Atlas rejects or ignores
    assert keywords(schema) <= KEYWORDS
    assert "_id" in schema["required"] and schema["additionalProperties"] is False


@pytest.mark.parametrize(
    ("model", "label"), [(m, label) for m, docs in INVALID.items() for label in docs]
)
def test_the_validator_rejects_what_the_model_rejects(model, label):
    doc = INVALID[model][label]

    with pytest.raises(ValidationError):
        model.model_validate(doc)
    assert not conforms(doc, validator(model)["$jsonSchema"])


MODEL_ONLY = {
    "report id not r_ and its primary article": (
        Report,
        change(report(), ["_id"], "r_x"),
    ),
    "embedding of 383 dimensions": (
        Report,
        change(
            report(),
            ["embedding"],
            Binary.from_vector([0.5] * 383, BinaryVectorDtype.FLOAT32),
        ),
    ),
    "embedding as plain bytes": (
        Report,
        change(report(), ["embedding"], Binary(b"\0" * 1536)),
    ),
    "case id not c_ and its report": (Case, change(case(), ["_id"], "c_r_other")),
    "first year after the last": (Place, change(place(), ["first_year"], 1920)),
    "stat id not its scope and year": (Stat, change(stat(), ["_id"], "year:1876")),
}


@pytest.mark.parametrize("label", MODEL_ONLY)
def test_the_model_checks_what_a_validator_cannot(label):
    model, doc = MODEL_ONLY[label]

    with pytest.raises(ValidationError):
        model.model_validate(doc)


def test_an_int8_embedding_is_stored_as_given():
    doc = change(
        report(), ["embedding"], Binary.from_vector([7] * 384, BinaryVectorDtype.INT8)
    )

    assert stored(Report, doc) == doc


@pytest.mark.atlas
def test_atlas_rejects_what_the_model_rejects():
    uri = setting("MONGODB_URI")
    if not uri:
        pytest.skip("no MONGODB_URI, as in CI")
    with MongoClient(uri.get(), serverSelectionTimeoutMS=10_000) as client:
        db = client["paperghosts"]
        for model, docs in INVALID.items():
            scratch = db.create_collection(
                f"scratch_validator_{uuid.uuid4().hex[:8]}", validator=validator(model)
            )
            try:
                scratch.insert_one(VALID[model]())
                for label, doc in docs.items():
                    with pytest.raises(WriteError) as rejected:
                        scratch.insert_one(doc)
                    assert rejected.value.code == 121, label
            finally:
                scratch.drop()
