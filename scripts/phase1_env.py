"""Phase 1 environment facts for eval/results/phase1_env.json (BUILD-PLAN section 3).

Run with `uv run python scripts/phase1_env.py`. Ollama must be running, and the faro_1850
pass streams about 1 GB. Every fact is measured here, or is null with the reason why.
Failures are recorded by type only, because library messages can quote keys and URIs.
"""

import io
import json
import multiprocessing
import os
import platform
import shutil
import subprocess
import tarfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import orjson
import pymongo
import sentry_sdk
from pymongo.operations import SearchIndexModel

from paperghosts.config import setting
from paperghosts.observability.sentry import init_sentry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "results" / "phase1_env.json"
SKELETON = ROOT / "data" / "skeleton" / "stratford_1850.json"
FARO_1850 = (
    "https://huggingface.co/datasets/dell-research-harvard/AmericanStories"
    "/resolve/main/faro_1850.tar.gz"
)
GEMMA = "gemma4:26b-a4b-it-qat"


class Unknown(Exception):
    """A fact that couldn't be measured. We write the message, so it is safe to record."""


def unknown(reason):
    return {"value": None, "reason": reason}


def machine():
    def sysctl(name):
        run = subprocess.run(
            ["sysctl", "-n", name], capture_output=True, text=True, check=True
        )
        return run.stdout.strip()

    return {
        "chip": sysctl("machdep.cpu.brand_string"),
        "cores": os.cpu_count(),
        "ram_gib": round(int(sysctl("hw.memsize")) / 2**30, 1),
        "disk_free_gib": round(shutil.disk_usage(ROOT).free / 2**30, 1),
        "os": platform.platform(),
    }


def download(url, chunks):
    """Runs in its own process, so parsing can't slow the download it measures."""
    try:
        start, size = time.perf_counter(), 0
        with httpx.stream("GET", url, follow_redirects=True, timeout=60) as response:
            if response.status_code != 200:
                chunks.put({"error": f"HTTP {response.status_code}"})
                return
            for chunk in response.iter_raw(1 << 20):
                size += len(chunk)
                chunks.put(chunk)
        chunks.put({"bytes": size, "seconds": time.perf_counter() - start})
    except Exception as exc:  # noqa: BLE001  the reader reports it, and the type is enough
        chunks.put({"error": type(exc).__name__})


class Chunks(io.RawIOBase):
    """A readable stream over byte chunks from a queue, ended by the download's stats."""

    def __init__(self, chunks):
        self.chunks, self.buffer, self.done = chunks, memoryview(b""), None

    def readable(self):
        return True

    def readinto(self, out):
        while not self.buffer and self.done is None:
            item = self.chunks.get()
            if isinstance(item, dict):
                self.done = item
            else:
                self.buffer = memoryview(item)
        if self.done and "error" in self.done:
            raise Unknown(f"the faro_1850 download raised {self.done['error']}")
        n = min(len(out), len(self.buffer))
        out[:n] = self.buffer[:n]
        self.buffer = self.buffer[n:]
        return n

    def finish(self):
        """Drains whatever the tar reader left unread, and returns the download's stats."""
        while self.done is None:
            item = self.chunks.get()
            if isinstance(item, dict):
                self.done = item
        return self.done


def read_pages(stream):
    """Counts pages and articles in a faro tarball, and keeps every article that mentions
    Stratford and knocking, the ones naming Phelps first."""
    pages = articles = 0
    matches = []
    with tarfile.open(fileobj=stream, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            page = orjson.loads(tar.extractfile(member).read())
            pages += 1
            for article in page.get("full articles") or []:
                articles += 1
                text = article.get("article") or ""
                if "Stratford" in text and "knock" in text.lower():
                    context = {
                        key: page.get(key) for key in ("lccn", "edition", "scan")
                    }
                    matches.append(
                        {"member": member.name, "page": context, "article": article}
                    )
    matches.sort(
        key=lambda m: (
            "Phelps" not in m["article"]["article"],
            -len(m["article"]["article"]),
        )
    )
    return pages, articles, matches


def faro_1850():
    chunks = multiprocessing.Queue()
    downloader = multiprocessing.Process(target=download, args=(FARO_1850, chunks))
    downloader.start()
    try:
        stream = Chunks(chunks)
        cpu = time.process_time()
        pages, articles, matches = read_pages(io.BufferedReader(stream, 1 << 20))
        cpu = time.process_time() - cpu
        stats = stream.finish()
    finally:
        downloader.join(timeout=30)
        if downloader.is_alive():
            downloader.terminate()

    SKELETON.parent.mkdir(parents=True, exist_ok=True)
    SKELETON.write_bytes(orjson.dumps(matches, option=orjson.OPT_INDENT_2))
    download_rate = stats["bytes"] / 1e6 / stats["seconds"]
    parse_rate = stats["bytes"] / 1e6 / cpu
    first = matches[0] if matches else None
    return {
        "url": FARO_1850,
        "compressed_bytes": stats["bytes"],
        "download_seconds": round(stats["seconds"], 1),
        "download_mb_per_s": round(download_rate, 1),
        "pages": pages,
        "articles": articles,
        "parse_cpu_seconds": round(cpu, 1),
        "pages_per_s_one_core": round(pages / cpu),
        "articles_per_s_one_core": round(articles / cpu),
        "compressed_mb_per_s_one_core": round(parse_rate, 1),
        "cores_to_keep_up_with_download": round(download_rate / parse_rate, 1),
        "stratford_knockings": {
            # different articles, not copies of one story (decision 8)
            "matching_articles": len(matches),
            "naming_phelps": sum("Phelps" in m["article"]["article"] for m in matches),
            "saved_to": str(SKELETON.relative_to(ROOT)),
            "first": {
                "paper": first["page"]["lccn"]["title"],
                "date": first["page"]["edition"]["date"],
                "article_id": first["article"]["id"],
            },
        }
        if first
        else unknown("no 1850 article mentions both Stratford and knocking"),
    }


def ollama():
    try:
        response = httpx.post(
            "http://localhost:11434/api/generate",
            json={
                "model": GEMMA,
                "prompt": "Name the twelve months of the year, one per line.",
                "stream": False,
                "keep_alive": 0,  # unload right after, which gives back about 15 GB of RAM
                "options": {"num_predict": 128, "temperature": 0},
            },
            timeout=600,
        )
    except httpx.ConnectError as exc:
        raise Unknown("Ollama isn't running; start it with `ollama serve`") from exc
    if response.status_code != 200:
        raise Unknown(f"Ollama answered HTTP {response.status_code}")
    r = response.json()
    return {
        "model": GEMMA,
        "load_seconds": round(r["load_duration"] / 1e9, 1),
        "prompt_tokens": r["prompt_eval_count"],
        "prompt_tokens_per_s": round(
            r["prompt_eval_count"] / (r["prompt_eval_duration"] / 1e9)
        ),
        "generated_tokens": r["eval_count"],
        "generated_tokens_per_s": round(
            r["eval_count"] / (r["eval_duration"] / 1e9), 1
        ),
    }


def scratch_indexes(collection):
    """Creates one Atlas Search and one Vector Search index on a scratch collection, waits
    until both can be queried, then drops them and the collection."""
    vector = {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 4,
        "similarity": "cosine",
    }
    models = {
        "search": SearchIndexModel(
            {"mappings": {"dynamic": True}}, name="scratch_search"
        ),
        "vector_search": SearchIndexModel(
            {"fields": [vector]}, name="scratch_vector", type="vectorSearch"
        ),
    }
    results = {}
    collection.insert_one({"text": "scratch", "embedding": [0.1, 0.2, 0.3, 0.4]})
    try:
        start = time.perf_counter()
        for kind, model in models.items():
            try:
                collection.create_search_index(model)
                results[kind] = {"created": True}
            except pymongo.errors.PyMongoError as exc:
                code = getattr(exc, "code", None)
                results[kind] = {
                    "created": False,
                    "reason": f"{type(exc).__name__}, code {code}",
                }
        waiting = {
            m.document["name"]: k for k, m in models.items() if results[k]["created"]
        }
        while waiting and time.perf_counter() - start < 300:
            time.sleep(2)
            for index in collection.list_search_indexes():
                kind = waiting.get(index["name"])
                if kind and (index.get("queryable") or index.get("status") == "FAILED"):
                    ready = round(time.perf_counter() - start, 1)
                    failed = unknown("the index build failed")
                    results[kind]["seconds_to_queryable"] = (
                        failed if not index.get("queryable") else ready
                    )
                    del waiting[index["name"]]
        for kind in waiting.values():
            results[kind]["seconds_to_queryable"] = unknown(
                "not queryable within 300 s"
            )
        for kind, model in models.items():
            if results[kind]["created"]:
                collection.drop_search_index(model.document["name"])
                results[kind]["dropped"] = True
    finally:
        collection.drop()
    return results


def atlas():
    tier_reason = (
        "the driver can't read the tier, and the Atlas Admin API needs an Atlas API key, "
        "which .env doesn't have"
    )
    with pymongo.MongoClient(
        setting("MONGODB_URI").get(), serverSelectionTimeoutMS=10_000
    ) as client:
        sizes = {db["name"]: db["sizeOnDisk"] for db in client.list_databases()}
        return {
            "version": client.server_info()["version"],
            "tier": unknown(tier_reason),
            "storage_limit": unknown(tier_reason),
            "storage_used_bytes": sum(sizes.values()),
            "storage_used_bytes_by_database": sizes,
            "indexes": scratch_indexes(client["paperghosts"]["scratch_phase1_env"]),
        }


def serpapi():
    key = setting("SERPAPI_API_KEY").get()
    if not key:
        raise Unknown("SERPAPI_API_KEY is empty")
    response = httpx.get(
        "https://serpapi.com/account.json", params={"api_key": key}, timeout=15
    )
    if response.status_code != 200:
        raise Unknown(f"the account endpoint answered HTTP {response.status_code}")
    return {
        "searches_left": int(response.json()["total_searches_left"]),
        "source": "the account endpoint, which uses no searches",
    }


def ultramarine():
    key, base, model = (
        setting(name).get()
        for name in ("ULTRAMARINE_API_KEY", "ULTRAMARINE_BASE_URL", "ULTRAMARINE_MODEL")
    )
    if not (key and base and model):
        raise Unknown("the Ultramarine key, base URL or model is empty")
    start = time.perf_counter()
    response = httpx.post(
        f"{base.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with the one word: ready"}],
            "max_tokens": 8,
            "temperature": 0,
        },
        timeout=60,
    )
    latency = time.perf_counter() - start
    if response.status_code != 200:
        raise Unknown(f"chat completions answered HTTP {response.status_code}")
    body = response.json()
    usage = body.get("usage")
    words = ("cost", "credit", "price", "billing")
    headers = {
        k: v for k, v in response.headers.items() if any(w in k.lower() for w in words)
    }
    cost = body.get("cost") or (usage or {}).get("cost") or headers or None
    return {
        "model": body.get("model"),
        "usage": usage,  # exactly as reported
        "cost": cost
        if cost is not None
        else unknown("no cost in the body or the headers"),
        "latency_seconds": round(latency, 2),
    }


def tinker_facts():
    import tinker  # takes 2.5 s, so only when this section runs

    with tinker.ServiceClient(api_key=setting("TINKER_API_KEY").get()) as service:
        capabilities = service.get_server_capabilities()
    return {
        "base_models": [
            {
                "name": m.model_name,
                "trainable": m.trainable,
                "sampleable": m.sampleable,
                "max_context_length": m.max_context_length,
            }
            for m in capabilities.supported_models
        ],
        "credits": unknown(
            "the API reports usage and estimated gross cost, not the remaining balance"
        ),
        "lora_weights_download": {
            "documented": True,
            "how": (
                "save_weights_external, then RestClient.get_external_weights_urls gives a "
                f"signed URL per file (tinker SDK {tinker.__version__})"
            ),
            "verified": False,
            "verify_in": "Phase 2C, after the first training run",
        },
    }


def sentry_event():
    if not init_sentry("pipeline"):
        raise Unknown("SENTRY_DSN is empty")
    event_id = sentry_sdk.capture_message("phase1_env test event", level="info")
    sentry_sdk.flush(timeout=10)
    org, token = setting("SENTRY_ORG").get(), setting("SENTRY_AUTH_TOKEN").get()
    url = f"https://sentry.io/api/0/organizations/{org}/eventids/{event_id}/"
    start = time.perf_counter()
    while time.perf_counter() - start < 120:
        response = httpx.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if response.status_code == 200:
            return {
                "event_id": event_id,
                "read_back_from_project": response.json()["projectSlug"],
                "seconds_to_read_back": round(time.perf_counter() - start, 1),
                "web_dsn": unknown(
                    "proven in Phase 4, when the React SDK sends the site's first event"
                ),
            }
        if response.status_code != 404:
            raise Unknown(f"the Sentry API answered HTTP {response.status_code}")
        time.sleep(3)
    raise Unknown(f"event {event_id} was not readable through the API within 120 s")


SECTIONS = {
    "machine": machine,
    "faro_1850": faro_1850,
    "ollama": ollama,
    "atlas": atlas,
    "serpapi": serpapi,
    "ultramarine": ultramarine,
    "tinker": tinker_facts,
    "sentry": sentry_event,  # last: once Sentry is on, later errors would become events
}


def measure(key, section):
    print(f"{key} ...", flush=True)
    start = time.perf_counter()
    try:
        facts = section()
    except Unknown as exc:
        facts = unknown(str(exc))
    except Exception as exc:  # noqa: BLE001  library messages can quote keys and URIs
        facts = unknown(f"{section.__name__} raised {type(exc).__name__}")
    print(f"{key} done in {time.perf_counter() - start:.0f} s", flush=True)
    return facts


def code_version():
    def git(*args):
        run = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        )
        return run.stdout.strip()

    return git("rev-parse", "--short", "HEAD") + (
        "-dirty" if git("status", "--porcelain") else ""
    )


def main():
    facts = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "command": "uv run python scripts/phase1_env.py",
        "code_version": code_version(),
    }
    for key, section in SECTIONS.items():
        facts[key] = measure(key, section)
    OUT.write_text(json.dumps(facts, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
