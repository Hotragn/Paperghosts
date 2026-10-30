"""make worker: runs the workflows and activities against the local Temporal dev server."""

import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from temporalio.client import Client
from temporalio.worker import SharedStateManager, Worker

from paperghosts.ingest.year import available_years, ingest_year
from paperghosts.observability.sentry import init_sentry
from paperghosts.workflows import TASK_QUEUE, TEMPORAL
from paperghosts.workflows.ingest import IngestArchiveWorkflow
from paperghosts.workflows.smoke import SmokeWorkflow, count_steps


async def main():
    init_sentry("pipeline")
    client = await Client.connect(TEMPORAL)
    spawn = multiprocessing.get_context("spawn")
    # each year gets a fresh process: four cores past the GIL, and its own peak memory
    with ProcessPoolExecutor(
        max_workers=4, mp_context=spawn, max_tasks_per_child=1
    ) as pool:
        worker = Worker(
            client,
            task_queue=TASK_QUEUE,
            workflows=[SmokeWorkflow, IngestArchiveWorkflow],
            activities=[count_steps, ingest_year, available_years],
            activity_executor=pool,
            shared_state_manager=SharedStateManager.create_from_multiprocessing(
                spawn.Manager()
            ),
        )
        print(f"worker polling task queue {TASK_QUEUE!r} on {TEMPORAL}", flush=True)
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
