"""make api: the read-only API over MongoDB Atlas: the walking skeleton, and the Morgue's Atlas
Search routes. Each Atlas query runs in a Sentry span (op db.atlas.query) that carries its kind
and latency, never the words searched for."""

import time
from contextlib import asynccontextmanager
from importlib.metadata import version

import sentry_sdk
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pymongo import AsyncMongoClient

from paperghosts.config import setting
from paperghosts.observability.sentry import init_sentry
from paperghosts.store.search import fuzzy, like


@asynccontextmanager
async def lifespan(app):
    init_sentry("api")
    client = AsyncMongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=5_000
    )
    app.state.db = client["paperghosts"]
    yield
    await client.close()


app = FastAPI(title="Paper Ghosts", lifespan=lifespan)


@app.get("/api/health")
async def health():
    try:
        await app.state.db.command("ping")
        atlas = True
    except Exception:  # noqa: BLE001  any failure means Atlas can't be reached from here
        atlas = False
    return {"ok": True, "atlas": atlas, "version": version("paperghosts")}


@app.get("/api/skeleton/{article_id}")
async def skeleton(article_id: str):
    article = await app.state.db.skeleton.find_one({"_id": article_id})
    if article is None:
        error = {"code": "not_found", "message": "No skeleton article has that id."}
        return JSONResponse({"error": error}, status_code=404)
    return article


def listed(report: dict) -> dict:
    """A search result as the API gives it: its article id in place of the stored _id."""
    rest = {k: v for k, v in report.items() if k != "_id"}
    return {"article_id": report["_id"].removeprefix("r_"), **rest}


async def traced(kind: str, pipeline: list) -> list:
    """An aggregation on reports, in a span that records its query kind and latency."""
    with sentry_sdk.start_span(op="db.atlas.query", name=f"reports {kind}") as span:
        span.set_data("query.kind", kind)
        sentry_sdk.set_tag("query.kind", kind)
        started = time.perf_counter()
        found = await (await app.state.db.reports.aggregate(pipeline)).to_list()
        span.set_data("latency_ms", round((time.perf_counter() - started) * 1000, 1))
        span.set_data("results", len(found))
    return found


@app.get("/api/search")
async def search(q: str = Query(min_length=2, max_length=100)):
    """Reports matching a town or word, fuzzily, so the OCR's misreadings still match."""
    found = await traced("fuzzy", fuzzy(q))
    return {"results": [listed(r) for r in found]}


@app.get("/api/like/{article_id}")
async def ghosts_like(article_id: str):
    """The five reports Atlas Search's moreLikeThis ranks closest to this one."""
    with sentry_sdk.start_span(op="db.atlas.query", name="reports find") as span:
        span.set_data("query.kind", "find")
        doc = await app.state.db.reports.find_one(
            {"_id": f"r_{article_id}"}, {"headline": 1, "text": 1}
        )
    if doc is None:
        error = {"code": "not_found", "message": "No report has that id."}
        return JSONResponse({"error": error}, status_code=404)
    found = await traced("more_like_this", like(doc))
    return {"results": [listed(r) for r in found]}
