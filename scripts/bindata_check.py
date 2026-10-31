"""BinData vectors on M0 (decision 32, rule 6): float32 and int8 vectors at the embedding's
dimension, in a scratch collection with one Vector Search index over both. Each query is run
exactly and approximately, and its nearest neighbours are checked against numpy's. The scratch
collection and its index are removed afterwards, so the plan's three Search indexes fit M0's
cap of three. Writes eval/results/phase2b/bindata_check.json."""

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import bson
import numpy as np
from bson.binary import Binary, BinaryVectorDtype
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

from paperghosts.config import setting
from paperghosts.schemas import DIMENSIONS

OUT = Path(__file__).parents[1] / "eval" / "results" / "phase2b" / "bindata_check.json"
DOCS, CLUSTERS, QUERIES, K, CANDIDATES = 2_000, 40, 20, 10, 200
TYPES = {"float32": BinaryVectorDtype.FLOAT32, "int8": BinaryVectorDtype.INT8}


def vectors(seed=20261030):
    """Documents and queries in clusters, as embeddings of similar stories are, so the nearest
    neighbours are well apart from the rest; int8 is each float32 vector scaled to ±127."""
    rng = np.random.default_rng(seed)
    centres = rng.normal(size=(CLUSTERS, DIMENSIONS))
    docs = centres[np.arange(DOCS) % CLUSTERS] + 0.6 * rng.normal(
        size=(DOCS, DIMENSIONS)
    )
    queries = centres[rng.integers(CLUSTERS, size=QUERIES)] + 0.6 * rng.normal(
        size=(QUERIES, DIMENSIONS)
    )
    floats = {"docs": docs.astype(np.float32), "queries": queries.astype(np.float32)}
    ints = {
        name: np.round(v * (127 / np.abs(v).max(axis=1, keepdims=True))).astype(np.int8)
        for name, v in floats.items()
    }
    return {"float32": floats, "int8": ints}


def nearest(docs, query, k=K):
    """numpy's k nearest by cosine, ties to the lower id, and their Atlas scores, (1 + cos) / 2."""
    docs, query = docs.astype(np.float64), query.astype(np.float64)
    cos = docs @ query / (np.linalg.norm(docs, axis=1) * np.linalg.norm(query))
    order = np.lexsort((np.arange(len(docs)), -cos))[:k]
    return [int(i) for i in order], [(1 + float(cos[i])) / 2 for i in order]


def field_bytes(value):
    """The BSON bytes an embedding takes in a document, under the key "embedding"."""
    return len(bson.encode({"embedding": value})) - len(bson.encode({}))


def wait(collection, name, until, seconds=600):
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        found = {i["name"]: i for i in collection.list_search_indexes()}
        if until(found.get(name)):
            return round(time.perf_counter() - start, 1)
        time.sleep(3)
    raise TimeoutError(f"search index {name} not ready after {seconds} s")


def main():
    data = vectors()
    sample = data["float32"]["docs"][0]
    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dimensions": DIMENSIONS,
        "docs": DOCS,
        "queries": QUERIES,
        "k": K,
        "num_candidates": CANDIDATES,
        "embedding_bson_bytes": {
            "array_of_doubles": field_bytes([float(x) for x in sample]),
            "float32": field_bytes(
                Binary.from_vector(sample.tolist(), TYPES["float32"])
            ),
            "int8": field_bytes(
                Binary.from_vector(data["int8"]["docs"][0].tolist(), TYPES["int8"])
            ),
        },
    }
    name = "scratch_bindata"
    with MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        scratch = client["paperghosts"][f"scratch_bindata_{uuid.uuid4().hex[:8]}"]
        try:
            scratch.insert_many(
                [
                    {
                        "_id": i,
                        **{
                            kind: Binary.from_vector(
                                data[kind]["docs"][i].tolist(), dtype
                            )
                            for kind, dtype in TYPES.items()
                        },
                    }
                    for i in range(DOCS)
                ]
            )
            fields = [
                {
                    "type": "vector",
                    "path": kind,
                    "numDimensions": DIMENSIONS,
                    "similarity": "cosine",
                }
                for kind in TYPES
            ]
            scratch.create_search_index(
                SearchIndexModel({"fields": fields}, name=name, type="vectorSearch")
            )
            report["seconds_to_queryable"] = wait(
                scratch, name, lambda index: index and index.get("queryable")
            )
            for kind, dtype in TYPES.items():
                report[kind] = check(scratch, name, kind, dtype, data[kind])
        finally:
            for index in scratch.list_search_indexes():
                scratch.drop_search_index(index["name"])
            report["seconds_to_drop_index"] = wait(
                scratch, name, lambda index: index is None
            )
            scratch.drop()
            report["cleaned_up"] = {
                "scratch_collection_left": scratch.name
                in client["paperghosts"].list_collection_names(),
                "search_indexes_left_on_it": len(list(scratch.list_search_indexes())),
            }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1) + "\n")
    for kind in TYPES:
        r = report[kind]
        print(
            f"{kind}: exact {r['exact']['same_neighbours']}/{QUERIES} same neighbours, "
            f"{r['exact']['same_order']}/{QUERIES} same order, max score error "
            f"{r['exact']['max_score_error']:.2e}; approximate recall@{K} "
            f"{r['approximate']['recall']:.3f}"
        )
    print(f"wrote {OUT.relative_to(OUT.parents[3])}")


def check(collection, index, kind, dtype, data):
    exact = {"same_neighbours": 0, "same_order": 0, "max_score_error": 0.0}
    recall = []
    for query in data["queries"]:
        want, scores = nearest(data["docs"], query)
        stage = {
            "index": index,
            "path": kind,
            "queryVector": Binary.from_vector(query.tolist(), dtype),
            "limit": K,
        }
        project = {"$project": {"score": {"$meta": "vectorSearchScore"}}}
        hits = list(
            collection.aggregate([{"$vectorSearch": stage | {"exact": True}}, project])
        )
        got = [hit["_id"] for hit in hits]
        exact["same_neighbours"] += set(got) == set(want)
        exact["same_order"] += got == want
        error = max(abs(h["score"] - s) for h, s in zip(hits, scores, strict=True))
        exact["max_score_error"] = max(exact["max_score_error"], error)
        stage |= {"numCandidates": CANDIDATES}
        found = {hit["_id"] for hit in collection.aggregate([{"$vectorSearch": stage}])}
        recall.append(len(found & set(want)) / K)
    return {"exact": exact, "approximate": {"recall": sum(recall) / len(recall)}}


if __name__ == "__main__":
    main()
