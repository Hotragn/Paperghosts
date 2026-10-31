"""The API's Atlas query latency as Sentry measured it: p50, p95 and count for each span of op
db.atlas.query, by its name (reports fuzzy, reports more_like_this, reports find), over the last
SINCE of traffic, from Sentry's spans dataset with SENTRY_AUTH_TOKEN, which is never printed.

  uv run python scripts/sentry_latency.py [SINCE [RELEASE]]   SINCE defaults to 24h; RELEASE, a
                                                              commit SHA, keeps one release's spans
Writes eval/results/sentry_latency.json, keyed by release.
"""

import json
import sys
from datetime import UTC, datetime

import httpx
from label_gold import ROOT

from paperghosts.config import setting

RESULT = ROOT / "eval" / "results" / "sentry_latency.json"
ORG, PROJECT = "hotragn", "paperghosts-api"
FIELDS = ["span.description", "p50(span.duration)", "p95(span.duration)", "count()"]


def main(since: str = "24h", release: str = "") -> None:
    headers = {"Authorization": f"Bearer {setting('SENTRY_AUTH_TOKEN').get()}"}
    with httpx.Client(
        base_url="https://sentry.io/api/0", headers=headers, timeout=30
    ) as sentry:
        projects = {
            p["slug"]: p["id"]
            for p in sentry.get(f"/organizations/{ORG}/projects/").json()
        }
        answer = sentry.get(
            f"/organizations/{ORG}/events/",
            params={
                "dataset": "spans",
                "field": FIELDS,
                "query": "span.op:db.atlas.query"
                + (f" release:{release}" if release else ""),
                "project": projects[PROJECT],
                "statsPeriod": since,
                "sort": "-count()",
            },
        )
        answer.raise_for_status()
    rows = answer.json()["data"]
    found = {
        "release": release or "all",
        "project": PROJECT,
        "since": since,
        "pulled_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "spans": [
            {
                "query": r["span.description"],
                "p50_ms": round(r["p50(span.duration)"], 1),
                "p95_ms": round(r["p95(span.duration)"], 1),
                "count": r["count()"],
            }
            for r in rows
        ],
    }
    every = json.loads(RESULT.read_text()) if RESULT.exists() else {}
    every = every if "spans" not in every else {}  # an older single-run file
    every[found["release"]] = found
    RESULT.write_text(json.dumps(every, indent=1) + "\n")
    print(json.dumps(found, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
