"""Secrets, private notes and bulk data must never reach git; manifests must."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("path", "ignored"),
    [
        (".env", True),
        (".env.local", True),
        ("web/.env.local", True),
        ("Docs/IDEAS.md", True),
        ("data/candidates/1850.jsonl.zst", True),
        ("data/samples/1850.jsonl.zst", True),
        ("data/temporal/temporal.db", True),
        (".env.example", False),
        ("data/manifests/1850.json", False),
    ],
)
def test_private_files_stay_out_of_git(path, ignored):
    # a tracked file counts as not ignored, so a force-added .env fails too
    result = subprocess.run(["git", "check-ignore", "-q", path], check=False, cwd=ROOT)
    assert result.returncode in (0, 1), f"git check-ignore errored on {path}"
    assert (result.returncode == 0) == ignored
