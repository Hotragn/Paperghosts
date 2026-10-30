"""make db-init: the paperghosts database's collections, validators, indexes and Search indexes,
as ARCHITECTURE section 4 and decision 32 plan them. A second run changes nothing. It touches no
other database, and no collection outside the plan."""

from pymongo import ASCENDING, MongoClient
from pymongo.errors import OperationFailure
from pymongo.operations import IndexModel, SearchIndexModel

from paperghosts.config import setting
from paperghosts.schemas import DIMENSIONS, Case, Place, Report, Stat
from paperghosts.store.validators import validator

DATABASE = "paperghosts"
COLLECTIONS = {"reports": Report, "places": Place, "cases": Case, "stats": Stat}
STRICT = {"validationLevel": "strict", "validationAction": "error"}
CAP = "maximum number of FTS indexes"  # Atlas's error past the cap of Search indexes

# no category field (outcome, kind, place type, precision, decade, state) gets an index of its
# own: the Search and Vector Search indexes filter on them (decision 32, rule 4)
INDEXES = {
    "reports": [
        IndexModel([("location", "2dsphere")], name="location"),
        IndexModel(
            [("place_id", ASCENDING), ("date", ASCENDING)], name="place_id_date"
        ),
        IndexModel([("month_day", ASCENDING)], name="month_day"),
        # only the 30-60 investigated stories have a case
        IndexModel(
            [("case_id", ASCENDING)],
            name="case_id",
            unique=True,
            partialFilterExpression={"case_id": {"$exists": True}},
        ),
    ],
    "places": [IndexModel([("location", "2dsphere")], name="location")],
    "cases": [IndexModel([("report_id", ASCENDING)], name="report_id", unique=True)],
    "stats": [],
}


def value(kind):
    """A reader field, by its value alone: never its quote."""
    return {"type": "document", "fields": {"value": {"type": kind}}}


# static mappings of what is searched or filtered, and nothing else (decision 32, rule 5);
# three in all, M0's cap
SEARCH = {
    "reports": [
        SearchIndexModel(
            {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "headline": {"type": "string"},
                        "display_headline": {"type": "string"},
                        "text": {"type": "string"},
                        "town": {"type": "string"},
                        "state": {"type": "token"},
                        "decade": {"type": "number"},
                        "fields": {
                            "type": "document",
                            "fields": {
                                "place": value("string"),
                                "people": value("string"),
                                "seen": value("string"),
                                "specific_place": value("string"),
                                "outcome": value("token"),
                                "place_type": value("token"),
                                "precision": value("token"),
                            },
                        },
                    },
                }
            },
            name="reports_search",
            type="search",
        ),
        SearchIndexModel(
            {
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": DIMENSIONS,
                        "similarity": "cosine",
                    },
                    {"type": "filter", "path": "state"},
                    {"type": "filter", "path": "decade"},
                ]
            },
            name="reports_vector",
            type="vectorSearch",
        ),
    ],
    "places": [
        SearchIndexModel(
            {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "name": [{"type": "autocomplete"}, {"type": "string"}],
                        "alternate_names": {"type": "autocomplete"},
                        "state": {"type": "token"},
                    },
                }
            },
            name="places_search",
            type="search",
        ),
    ],
}


def same_index(current, spec):
    """Whether an index from index_information() is the one spec describes."""
    options = {k: v for k, v in spec.items() if k not in ("key", "name")}
    return list(current["key"]) == list(spec["key"].items()) and all(
        current.get(k) == v for k, v in options.items()
    )


def init(db):
    """Brings db to the plan. Returns what it changed (nothing, once it matches), and the
    Search indexes it couldn't create because the cluster already holds M0's cap of three."""
    changes, blocked = [], []
    existing = {c["name"]: c.get("options", {}) for c in db.list_collections()}
    for name, model in COLLECTIONS.items():
        wanted = {"validator": validator(model), **STRICT}
        if name not in existing:
            db.create_collection(name, **wanted)
            changes.append(f"created collection {name}")
        elif {k: existing[name].get(k) for k in wanted} != wanted:
            db.command("collMod", name, **wanted)
            changes.append(f"updated the validator of {name}")
        collection = db[name]
        searches = {index["name"]: index for index in collection.list_search_indexes()}
        for search in SEARCH.get(name, []):
            spec = search.document
            current = searches.get(spec["name"])
            if current is None:
                try:
                    collection.create_search_index(search)
                except OperationFailure as exc:
                    # the cap counts every database's Search indexes, not just ours
                    if CAP not in str(exc):
                        raise
                    blocked.append(f"{name}.{spec['name']}")
                    continue
                changes.append(f"created search index {name}.{spec['name']}")
            elif current.get("latestDefinition") != spec["definition"]:
                collection.update_search_index(spec["name"], spec["definition"])
                changes.append(f"updated search index {name}.{spec['name']}")
        have = collection.index_information()
        for index in INDEXES[name]:
            spec = index.document
            current = have.get(spec["name"])
            if current is not None and same_index(current, spec):
                continue
            if current is not None:
                collection.drop_index(spec["name"])
            collection.create_indexes([index])
            done = "rebuilt" if current is not None else "created"
            changes.append(f"{done} index {name}.{spec['name']}")
    return changes, blocked


def main():
    with MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        db = client[DATABASE]
        changes, blocked = init(db)
        print("\n".join(changes) if changes else "nothing to change")
        for name in SEARCH:
            for index in db[name].list_search_indexes():
                ready = "queryable" if index.get("queryable") else "not queryable yet"
                print(
                    f"search index {name}.{index['name']}: {index.get('status')}, {ready}"
                )
        if blocked:
            print(
                f"not created: {', '.join(blocked)}. M0 allows three Search indexes in the "
                "whole cluster, and other databases already hold some of them."
            )
            raise SystemExit(1)


if __name__ == "__main__":
    main()
