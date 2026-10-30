"""Temporal workflows, activities and the worker."""

import os

TEMPORAL = "localhost:7233"  # the dev server `make temporal` starts
TASK_QUEUE = "paperghosts"


def identity(role):
    """pid@paperghosts-role: the SDK's default, pid@host, would put the machine's name in
    every workflow history (decision 24)."""
    return f"{os.getpid()}@paperghosts-{role}"
