"""make ingest: IngestArchiveWorkflow runs the year activity over AmericanStories, at most
four years at a time. Pass the years, or none for every year in the dataset. Needs
make temporal and make worker running."""

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from temporalio import workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from paperghosts.ingest.year import available_years, ingest_year
    from paperghosts.workflows import TASK_QUEUE, TEMPORAL, identity

RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,
)


@dataclass
class IngestRequest:
    # no years means every year in the dataset
    years: list[int] = field(default_factory=list)
    # one core prefilters about 21 MB/s, so four keep up with the download
    concurrency: int = 4


@workflow.defn
class IngestArchiveWorkflow:
    @workflow.run
    async def run(self, request: IngestRequest) -> list[dict]:
        years = request.years or await workflow.execute_activity(
            available_years,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RETRY,
        )
        gate = asyncio.Semaphore(request.concurrency)

        async def one(year):
            async with gate:
                try:
                    return await workflow.execute_activity(
                        ingest_year,
                        year,
                        activity_id=f"faro_{year}",  # names the year in the UI and history
                        start_to_close_timeout=timedelta(hours=2),
                        heartbeat_timeout=timedelta(minutes=2),
                        retry_policy=RETRY,
                    )
                except ActivityError as exc:
                    # list the failure, and let the other years carry on
                    return {"year": year, "failed": str(exc.cause or exc)}

        return list(await asyncio.gather(*(one(year) for year in years)))


async def main(years):
    client = await Client.connect(TEMPORAL, identity=identity("ingest"))
    workflow_id = "ingest-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    results = await client.execute_workflow(
        IngestArchiveWorkflow.run,
        IngestRequest(years=years),
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )
    print(f"workflow {workflow_id}")
    for r in results:
        if "failed" in r:
            print(f"{r['year']}  FAILED: {r['failed']}")
            continue
        out = sum(r["output_bytes"].values()) / 1e6
        how = "skipped, already done" if r["skipped"] else f"attempt {r['attempt']}"
        print(
            f"{r['year']}  {r['seconds']:7.1f} s  {r['articles']:>10,} articles  "
            f"{r['candidates']:>7,} candidates  {out:7.1f} MB out  "
            f"{r['peak_rss_bytes'] / 1e6:5.0f} MB peak  ({how})"
        )


if __name__ == "__main__":
    asyncio.run(main([int(year) for year in sys.argv[1:]]))
