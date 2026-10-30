"""make api: the read-only API over MongoDB Atlas. Phase 1 serves the walking skeleton."""

from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pymongo import AsyncMongoClient

from paperghosts.config import setting
from paperghosts.observability.sentry import init_sentry


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
