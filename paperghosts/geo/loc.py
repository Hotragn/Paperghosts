"""Library of Congress title records (decision 34), asked for only where they're needed: for the
LCCNs whose title strings name no place or state, for the papers of the geocoder's accuracy
draw, and in 2D for the papers among stored printings. Each is asked for once, at most one
request every 3.5 s, as loc.gov's JSON API allows (crops.get, decision 29). It is cached on
disk with its URL, the date it was retrieved and its status, so a 404 isn't asked for twice
either."""

import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx

from paperghosts.ingest.crops import get

CACHE = Path(__file__).parents[2] / "data" / "loc" / "titles"
COUNTS = Counter()  # requests made, and cache hits


def title_record(lccn: str, cache: Path = CACHE) -> dict:
    """The cached record of loc.gov's item for lccn: its url, retrieved, status and body."""
    path = cache / f"{lccn}.json"
    if path.exists():
        COUNTS["cache_hits"] += 1
        return json.loads(path.read_text())
    url = f"https://www.loc.gov/item/{lccn}/"
    COUNTS["requests"] += 1
    try:
        response = get(url, fo="json")
        status, body = response.status_code, response.json()
    except httpx.HTTPStatusError as exc:
        status, body = exc.response.status_code, None
        if status != 404 and status < 500:
            raise
    record = {
        "url": f"{url}?fo=json",
        "retrieved": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": status,
        "body": body,
    }
    if (
        status >= 500
    ):  # still failing after get's retries: not cached, so asked again later
        COUNTS["errors"] += 1
        return record
    cache.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.{os.getpid()}.partial")
    partial.write_text(json.dumps(record))
    partial.replace(path)
    return record


def recorded(record: dict) -> dict | None:
    """The place, state and county a title record gives, as catalogued today, with its title
    and years; None for a record loc.gov doesn't have. A paper that moved has all its counties
    and states: Zajedničar's are Allegheny, Pa. and Mahoning, Ohio."""
    item = (record.get("body") or {}).get("item")
    if record.get("status") != 200 or not item:
        return None
    where = (item.get("location_str") or "").split(";")[0].strip()
    place, _, state = where.rpartition(", ")
    counties = [c.title() for c in item.get("location_county") or []]
    states = [s.title() for s in item.get("location_state") or []]
    return {
        "place": place or None,
        "state": state or None,
        "county": counties[0] if counties else None,
        "counties": counties,
        "states": states or ([state] if state else []),
        "title": item.get("title"),
        "years": item.get("dates_of_publication"),
    }
