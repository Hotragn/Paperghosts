"""make worker: runs the workflows and activities against the local Temporal dev server."""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from paperghosts.observability.sentry import init_sentry
from paperghosts.workflows import TASK_QUEUE, TEMPORAL
from paperghosts.workflows.smoke import SmokeWorkflow, count_steps


async def main():
    init_sentry("pipeline")
    client = await Client.connect(TEMPORAL)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SmokeWorkflow],
        activities=[count_steps],
    )
    print(f"worker polling task queue {TASK_QUEUE!r} on {TEMPORAL}", flush=True)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
