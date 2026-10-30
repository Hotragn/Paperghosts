"""IngestArchiveWorkflow skips a year whose manifest matches the current versions, runs a
stale year again, and retries a year whose stream drops. It runs in Temporal's test
environment, on a two-article year file, with threads standing in for the process pool."""

import asyncio
import io
import json
import shutil
import tarfile
import uuid
from concurrent.futures import ThreadPoolExecutor

import orjson
import zstandard
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from paperghosts.ingest import lexicon, year
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


def test_a_finished_year_is_skipped_and_a_stale_one_runs_again(tmp_path, monkeypatch):
    data = setup(tmp_path, monkeypatch)
    manifest = data / "manifests" / "1850.json"
    manifest.parent.mkdir(parents=True)
    current = {"lexicon_version": lexicon.VERSION, "code_version": year.code_version()}

    async def steps(client):
        manifest.write_text(json.dumps({"year": 1850, **current, "candidates": 7}))
        skipped = await ingest(client, [1850])
        streamed = (data / "candidates" / "1850.jsonl.zst").exists()
        manifest.write_text(
            json.dumps({"year": 1850, **current, "code_version": "stale"})
        )
        return skipped, streamed, await ingest(client, [1850])

    [skipped], streamed_when_skipped, [rerun] = asyncio.run(in_test_environment(steps))

    assert (
        skipped["skipped"] is True and skipped["candidates"] == 7
    )  # the stored record
    assert streamed_when_skipped is False
    assert rerun["skipped"] is False and rerun["candidates"] == 1
    assert json.loads(manifest.read_text())["code_version"] == current["code_version"]
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
