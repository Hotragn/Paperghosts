"""The smoke workflow survives its injected failure: the retry policy runs the activity again,
and the second attempt picks up after the first attempt's last heartbeat."""

import asyncio
import shutil
import uuid

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from paperghosts.workflows.smoke import SmokeWorkflow, count_steps


async def run_smoke():
    # Temporal's test environment: a throwaway server on a free port, not `make temporal`
    temporal = shutil.which("temporal")  # None in CI, where the SDK fetches its own
    async with (
        await WorkflowEnvironment.start_local(dev_server_existing_path=temporal) as env,
        Worker(
            env.client,
            task_queue="test",
            workflows=[SmokeWorkflow],
            activities=[count_steps],
        ),
    ):
        return await env.client.execute_workflow(
            SmokeWorkflow.run, 6, id=f"smoke-test-{uuid.uuid4()}", task_queue="test"
        )


def test_smoke_recovers_through_its_retry_policy():
    result = asyncio.run(run_smoke())
    assert result["attempt"] == 2
    # the failed attempt's heartbeats reached the server
    assert result["resumed_after"] >= 1
