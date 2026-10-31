"""Library of Congress title records (decision 34), asked for only where they're needed: for the
LCCNs whose title strings name no place or state, for the papers of the geocoder's accuracy
draw, and in 2D for the papers among stored printings. Each is asked for once, at most one
request every 3.5 s, as loc.gov's JSON API allows (crops.get, decision 29). It is cached on
disk with its URL, the date it was retrieved and its status, so a 404 isn't asked for twice
either (crops.cached)."""

from collections import Counter
from pathlib import Path

from paperghosts.ingest.crops import cached

CACHE = Path(__file__).parents[2] / "data" / "loc" / "titles"
COUNTS = Counter()  # requests made, cache hits, and errors not cached


def title_record(lccn: str, cache: Path = CACHE) -> dict:
    """The cached record of loc.gov's item for lccn: its url, retrieved, status and body."""
    return cached(
        f"https://www.loc.gov/item/{lccn}/",
        path=cache / f"{lccn}.json",
        counts=COUNTS,
        fo="json",
    )


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
