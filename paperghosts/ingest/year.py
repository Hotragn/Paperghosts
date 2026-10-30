"""One year file in, and its candidates, counts, samples and manifest out (ARCHITECTURE
section 3.1). ingest_year is the Temporal activity; the worker runs each in its own process."""

import hashlib
import json
import os
import re
import resource
import sys
import time
import urllib.error
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

from temporalio import activity
from temporalio.exceptions import ApplicationError, CancelledError

from paperghosts.ingest import lexicon, prefilter, stream
from paperghosts.ingest.prefilter import scan, write_jsonl_zst
from paperghosts.ingest.stream import FARO, pages

DATA = Path(__file__).parents[2] / "data"
SOURCE = FARO
LISTING = "https://huggingface.co/api/datasets/dell-research-harvard/AmericanStories/tree/main"
HEARTBEAT_EVERY = 200  # pages


def code_version():
    """A hash of the code that shapes a year's outputs; changing that code re-runs the year."""
    files = (lexicon.__file__, prefilter.__file__, stream.__file__, __file__)
    return hashlib.sha256(b"".join(Path(f).read_bytes() for f in files)).hexdigest()[
        :12
    ]


def write_json(path, data):
    """Writes to a partial file first, like write_jsonl_zst, and renames it once complete."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.{os.getpid()}.partial")
    partial.write_text(json.dumps(data, indent=2) + "\n")
    partial.replace(path)


def peak_rss_bytes():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024  # Linux reports KiB


def counts(year, result):
    """The year's counts, in a fixed order, so a re-run diffs clean in git."""
    return {
        "year": year,
        "lexicon_version": lexicon.VERSION,
        "pages": result["pages"],
        "articles": result["articles"],
        "candidates": len(result["candidates"]),
        "near_miss": result["near_miss"],
        "by_term": dict(sorted(result["per_term"].items())),
        "only_by_term": dict(sorted(result["only"].items())),
        "by_state": {
            state: result["by_state"][state] for state in sorted(result["by_state"])
        },
    }


@activity.defn
def available_years() -> list[int]:
    """Every year AmericanStories has a file for, from the dataset's file list."""
    with urlopen(LISTING, timeout=60) as response:
        paths = [item["path"] for item in json.load(response)]
    return sorted(
        int(m[1]) for p in paths if (m := re.fullmatch(r"faro_(\d{4})\.tar\.gz", p))
    )


# as in the process pool, a cancel reaches a year only through is_cancelled()
@activity.defn(no_thread_cancel_exception=True)
def ingest_year(year: int) -> dict:
    """Streams one year file through the prefilter and writes its outputs, or skips a year
    whose manifest matches the current lexicon and code versions and whose every output is
    on disk at the size the manifest records."""
    manifest_path = DATA / "manifests" / f"{year}.json"
    outputs = {
        "candidates": DATA / "candidates" / f"{year}.jsonl.zst",
        "samples": DATA / "samples" / f"{year}.jsonl.zst",
        "counts": DATA / "counts" / f"{year}.json",
    }
    versions = {"lexicon_version": lexicon.VERSION, "code_version": code_version()}
    if manifest_path.exists():
        done = json.loads(manifest_path.read_text())
        sizes = done.get("output_bytes", {})
        # manifests and counts are in git but candidates and samples are not
        if all(done.get(key) == value for key, value in versions.items()) and all(
            path.exists() and path.stat().st_size == sizes.get(name)
            for name, path in outputs.items()
        ):
            return {**done, "skipped": True}

    url = SOURCE.format(year=year)
    started, clock = datetime.now(UTC), time.perf_counter()
    progress = {"members": 0, "bytes_read": 0}
    parent = os.getppid()

    def report(members, bytes_read):
        progress.update(members=members, bytes_read=bytes_read)
        if members % HEARTBEAT_EVERY == 0:
            activity.heartbeat(progress)
            # a retry may be running this year already, so a lost attempt writes nothing
            if os.getppid() != parent:
                raise CancelledError("the worker that started this attempt is gone")
            if activity.is_cancelled():
                raise CancelledError("this attempt was cancelled")

    try:
        result = scan(pages(url, report), year)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ApplicationError(
                f"faro_{year} is not in the dataset", non_retryable=True
            ) from exc
        raise

    write_jsonl_zst(outputs["candidates"], result["candidates"])
    samples = [
        {"sample": name, **item}
        for name, items in result["samples"].items()
        for item in items
    ]
    write_jsonl_zst(outputs["samples"], samples)
    write_json(outputs["counts"], counts(year, result))
    manifest = {
        "year": year,
        "source": url,
        "bytes_read": progress["bytes_read"],
        **versions,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": round(time.perf_counter() - clock, 1),
        "attempt": activity.info().attempt,
        "articles": result["articles"],
        "candidates": len(result["candidates"]),
        "output_bytes": {name: path.stat().st_size for name, path in outputs.items()},
        "peak_rss_bytes": peak_rss_bytes(),
    }
    write_json(
        manifest_path, manifest
    )  # last: a year counts as done only once all is written
    return {**manifest, "skipped": False}
