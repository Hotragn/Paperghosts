"""make db-init against a fake database: it builds the plan once, changes nothing the second
time, repairs what has drifted and leaves other collections alone. A Search index past M0's
cluster-wide cap of three is reported rather than crashed on. The plan keeps decision 32's rules:
three Search indexes, static mappings without printings or quotes, and no index on a category
field."""

import copy
import json

from pymongo.errors import OperationFailure

from paperghosts.store import db_init


class FakeCollection:
    def __init__(self, db):
        self.db = db
        self.indexes = {"_id_": {"v": 2, "key": [("_id", 1)]}}
        self.search = {}

    def index_information(self):
        return copy.deepcopy(self.indexes)

    def create_indexes(self, models):
        for model in models:
            spec = dict(model.document)
            name, key = spec.pop("name"), spec.pop("key")
            self.indexes[name] = {"v": 2, "key": list(key.items()), **spec}

    def drop_index(self, name):
        del self.indexes[name]

    def list_search_indexes(self):
        return [
            {"name": name, "type": kind, "latestDefinition": copy.deepcopy(definition)}
            for name, (kind, definition) in self.search.items()
        ]

    def create_search_index(self, model):
        used = self.db.elsewhere + sum(
            len(c.search) for c in self.db.collections.values()
        )
        if used >= 3:
            message = "The maximum number of FTS indexes has been reached for this instance size."
            raise OperationFailure(message, code=20)
        spec = model.document
        self.search[spec["name"]] = (spec["type"], copy.deepcopy(spec["definition"]))

    def update_search_index(self, name, definition):
        self.search[name] = (self.search[name][0], copy.deepcopy(definition))


class FakeDatabase:
    def __init__(self, elsewhere=0):
        self.elsewhere = elsewhere  # Search indexes in the cluster's other databases
        self.options = {"skeleton": {}}
        self.collections = {"skeleton": FakeCollection(self)}

    def list_collections(self):
        return [
            {"name": n, "options": copy.deepcopy(o)} for n, o in self.options.items()
        ]

    def create_collection(self, name, **options):
        self.options[name] = options
        self.collections[name] = FakeCollection(self)

    def command(self, command, name, **options):
        assert command == "collMod"
        self.options[name] = options

    def __getitem__(self, name):
        return self.collections[name]


def test_db_init_builds_the_plan_and_a_second_run_changes_nothing():
    db = FakeDatabase()

    first, _ = db_init.init(db)
    second, blocked = db_init.init(db)

    assert len(first) == 4 + 6 + 3  # collections, indexes beside _id, Search indexes
    assert second == [] and blocked == []
    assert db.options["skeleton"] == {} and db["skeleton"].indexes.keys() == {"_id_"}


def test_db_init_repairs_only_what_has_drifted():
    db = FakeDatabase()
    db_init.init(db)
    db.options["reports"]["validationAction"] = "warn"
    db["places"].drop_index("location")
    db["reports"].search["reports_vector"][1]["fields"][0]["numDimensions"] = 768

    changes, _ = db_init.init(db)

    assert changes == [
        "updated the validator of reports",
        "updated search index reports.reports_vector",
        "created index places.location",
    ]
    assert db_init.init(db) == ([], [])


def test_a_search_index_past_m0s_cap_is_reported_and_the_rest_is_built():
    db = FakeDatabase(elsewhere=1)

    changes, blocked = db_init.init(db)

    assert blocked == ["places.places_search"]
    assert len(changes) == 4 + 6 + 2
    # once a slot is free, the next run creates it, and the one after changes nothing
    db.elsewhere = 0
    assert db_init.init(db) == (["created search index places.places_search"], [])
    assert db_init.init(db) == ([], [])


def test_the_plan_fits_m0s_cap_of_three_search_indexes():
    assert sum(len(models) for models in db_init.SEARCH.values()) == 3


def test_search_mappings_are_static_and_skip_printings_and_quotes():
    for models in db_init.SEARCH.values():
        for model in models:
            definition = model.document["definition"]
            if model.document["type"] == "search":
                assert definition["mappings"]["dynamic"] is False
            mapped = json.dumps(definition)
            assert "printings" not in mapped and "quote" not in mapped


def test_no_index_of_its_own_on_a_category_field():
    category = {"outcome", "kind", "place_type", "precision", "decade", "state"}
    for models in db_init.INDEXES.values():
        for model in models:
            for field in model.document["key"]:
                assert not set(field.split(".")) & category, field
