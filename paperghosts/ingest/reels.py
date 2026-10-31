"""The reel-to-batch map (decision 35): each microfilm reel's LoC batches and the issues each
holds, from the batch paths in the candidates and samples. A page with no batch path gets its
batch from its reel here, by `pick`, and so its IIIF service from local data. Its page is
checked before its crop is shown (`crops.page_check`). scripts/reel_map.py builds the map."""

import json
import re
from collections import defaultdict
from datetime import date
from functools import cache
from pathlib import Path

MAP = Path(__file__).parents[2] / "data" / "reels" / "map.json"
VERSION = re.compile(r"_?ver(\d+)$")  # one batch is ncu_frankenver01


def build(paths) -> dict:
    """{lccn: {reel: {batch: [issues]}}}, from batch paths' (batch, lccn, reel, issue)."""
    found = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for batch, lccn, reel, issue in paths:
        found[lccn][reel][batch].add(issue)
    return {
        lccn: {
            reel: {batch: sorted(issues) for batch, issues in sorted(batches.items())}
            for reel, batches in sorted(on.items())
        }
        for lccn, on in sorted(found.items())
    }


def flagged(reel_map: dict):
    """(lccn, reel, batches) for each reel that holds more than one batch."""
    for lccn, on in reel_map.items():
        for reel, batches in on.items():
            if len(batches) > 1:
                yield lccn, reel, batches


def day(issue: str) -> int:
    """An issue's date as a day number: issues are named for their date and edition."""
    return date(int(issue[:4]), int(issue[4:6]), int(issue[6:8])).toordinal()


def version(batch: str) -> int:
    found = VERSION.search(batch)
    return int(found[1]) if found else 0


def ranked(batches: dict[str, list[str]], issue: str) -> list[str]:
    """A reel's batches in the order to try them for a page of `issue`. A batch name whose
    issue is nearer the page's in date comes first, a tie going to the name with more of the
    reel's issues. Within a name, its latest version comes first (ver02 before ver01), wherever
    its issues are. info.json decides: a batch that doesn't hold the page answers 404."""
    names, held = defaultdict(list), defaultdict(list)
    for batch, issues in batches.items():
        name = VERSION.sub("", batch)
        names[name].append(batch)
        held[name].extend(issues)
    for versions in names.values():
        versions.sort(key=version, reverse=True)
    order = list(names)
    if len(order) > 1:
        when = day(issue)
        order.sort(
            key=lambda n: (
                min(abs(day(i) - when) for i in held[n]),
                -len(held[n]),
                names[n][0],
            )
        )
    return [batch for name in order for batch in names[name]]


def pick(batches: dict[str, list[str]], issue: str) -> str:
    """The batch for a page of `issue` on a reel holding these batches: the first to try."""
    return ranked(batches, issue)[0]


@cache
def load(path: Path = MAP) -> dict:
    """The map scripts/reel_map.py wrote, or an empty one before it's built."""
    return json.loads(path.read_text()) if path.exists() else {}
