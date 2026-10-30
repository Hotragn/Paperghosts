"""IngestArchiveWorkflow skips a year only while its manifest and every output match, and
retries a year whose stream drops; an attempt that is cancelled or loses its worker stops
before it writes. It runs in Temporal's test environment, on a one-page year file, with
threads standing in for the process pool."""

import asyncio
import io
import json
import os
import shutil
import tarfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import orjson
import pytest
import zstandard
from temporalio.exceptions import CancelledError
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from paperghosts.ingest import year
from paperghosts.ingest.prefilter import write_jsonl_zst
from paperghosts.workflows.ingest import IngestArchiveWorkflow, IngestRequest

PAGE = {
    "lccn": {"title": "The test herald.", "lccn": "sn0", "state": "Connecticut"},
    "edition": {"date": "1850-04-12"},
    "scan": {"width": 10, "height": 10},
    "full articles": [
        {"id": "a0", "headline": "", "article": "A ghost was seen.", "bbox_list": []},
        {"id": "a1", "headline": "", "article": "Strange noises.", "bbox_list": []},
        {"id": "a2", "headline": "", "article": "Wheat is up.", "bbox_list": []},
    ],
}


def setup(tmp_path, monkeypatch):
    with tarfile.open(tmp_path / "faro_1850.tar.gz", "w:gz") as tar:
        data = orjson.dumps(PAGE)
        info = tarfile.TarInfo("faro_1850/page.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    monkeypatch.setattr(year, "DATA", tmp_path / "data")
    monkeypatch.setattr(year, "SOURCE", tmp_path.as_uri() + "/faro_{year}.tar.gz")
    return tmp_path / "data"


async def ingest(client, years):
    return await client.execute_workflow(
        IngestArchiveWorkflow.run,
        IngestRequest(years=years),
        id=f"ingest-test-{uuid.uuid4()}",
        task_queue="test",
    )


async def in_test_environment(steps):
    temporal = shutil.which("temporal")  # None in CI, where the SDK fetches its own
    async with (
        await WorkflowEnvironment.start_local(dev_server_existing_path=temporal) as env,
        Worker(
            env.client,
            task_queue="test",
            workflows=[IngestArchiveWorkflow],
            activities=[year.ingest_year, year.available_years],
            activity_executor=ThreadPoolExecutor(2),
        ),
    ):
        return await steps(env.client)


def test_a_year_is_skipped_only_while_its_manifest_and_every_output_match(
    tmp_path, monkeypatch
):
    data = setup(tmp_path, monkeypatch)
    manifest = data / "manifests" / "1850.json"

    async def steps(client):
        runs = [await ingest(client, [1850]), await ingest(client, [1850])]
        # a fresh clone: manifests and counts are in git, candidates and samples are not
        (data / "candidates" / "1850.jsonl.zst").unlink()
        runs.append(await ingest(client, [1850]))
        (data / "samples" / "1850.jsonl.zst").write_bytes(b"cut short")
        runs.append(await ingest(client, [1850]))
        stale = json.loads(manifest.read_text()) | {"code_version": "stale"}
        manifest.write_text(json.dumps(stale))
        runs.append(await ingest(client, [1850]))
        return [run for [run] in runs]

    first, again, cloned, cut, stale = asyncio.run(in_test_environment(steps))

    assert again == {**first, "skipped": True}  # the stored manifest, and no stream
    assert [run["skipped"] for run in (first, cloned, cut, stale)] == [False] * 4
    assert json.loads(manifest.read_text())["code_version"] == year.code_version()
    counts = json.loads((data / "counts" / "1850.json").read_text())
    assert (counts["pages"], counts["articles"], counts["candidates"]) == (1, 3, 1)
    assert counts["by_state"] == {
        "Connecticut": {"pages": 1, "articles": 3, "candidates": 1}
    }
    rows = list(zstandard.open(data / "samples" / "1850.jsonl.zst", "rt"))
    assert sorted(json.loads(r)["sample"] for r in rows) == [
        "near_miss",
        "random",
        "random",
    ]


def test_a_dropped_stream_is_retried(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    real_pages, calls = year.pages, []

    def drops_once(url, progress=None):
        calls.append(url)
        if len(calls) == 1:
            raise ConnectionResetError("the stream dropped")
        return real_pages(url, progress)

    monkeypatch.setattr(year, "pages", drops_once)

    [result] = asyncio.run(in_test_environment(lambda client: ingest(client, [1850])))

    assert len(calls) == 2
    assert (result["attempt"], result["candidates"]) == (2, 1)


def test_each_process_writes_its_own_partial_files(tmp_path, monkeypatch):
    # two attempts at one year can overlap, so they must never share a partial file
    renamed, real_replace = [], Path.replace

    def replace(self, target):
        renamed.append(self.name)
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", replace)
    write_jsonl_zst(tmp_path / "1850.jsonl.zst", [{"id": "a0"}])
    year.write_json(tmp_path / "1850.json", {"year": 1850})

    pid = os.getpid()
    assert renamed == [f"1850.jsonl.zst.{pid}.partial", f"1850.json.{pid}.partial"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["1850.json", "1850.jsonl.zst"]


@pytest.mark.parametrize("loss", ["cancelled", "worker gone"])
def test_an_attempt_stops_before_writing_once_cancelled_or_orphaned(
    tmp_path, monkeypatch, loss
):
    data = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(year, "HEARTBEAT_EVERY", 1)
    env = ActivityEnvironment()

    def on_heartbeat(*details):
        if loss == "cancelled":
            env.cancel()  # as the worker does once the server refuses a heartbeat
        else:
            monkeypatch.setattr(os, "getppid", lambda: 1)  # launchd adopts orphans

    env.on_heartbeat = on_heartbeat
    with pytest.raises(CancelledError):
        env.run(year.ingest_year, 1850)
    assert not data.exists()
