"""make smoke: one workflow whose activity heartbeats, fails once on purpose and recovers
through its retry policy. Needs `make temporal` and `make worker` running."""

import asyncio
from datetime import UTC, datetime, timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from paperghosts.workflows import TASK_QUEUE, TEMPORAL, identity


@activity.defn
async def count_steps(steps: int) -> dict:
    info = activity.info()
    # a retry resumes after the last step its failed attempt heartbeated
    done = info.heartbeat_details[0] if info.heartbeat_details else 0
    for step in range(done + 1, steps + 1):
        await asyncio.sleep(0.1)
        activity.heartbeat(step)
        if info.attempt == 1 and step == steps // 2:
            raise ApplicationError(f"injected failure at step {step}")
    return {"attempt": info.attempt, "resumed_after": done}


@workflow.defn
class SmokeWorkflow:
    @workflow.run
    async def run(self, steps: int) -> dict:
        return await workflow.execute_activity(
            count_steps,
            steps,
            start_to_close_timeout=timedelta(seconds=30),
            heartbeat_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1), maximum_attempts=3
            ),
        )


async def main():
    client = await Client.connect(TEMPORAL, identity=identity("smoke"))
    workflow_id = "smoke-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    result = await client.execute_workflow(
        SmokeWorkflow.run,
        6,
        id=workflow_id,
        task_queue=TASK_QUEUE,
        execution_timeout=timedelta(seconds=60),
    )
    print(f"workflow {workflow_id}: {result}")
    print(f"history: http://localhost:8233/namespaces/default/workflows/{workflow_id}")


if __name__ == "__main__":
    asyncio.run(main())
