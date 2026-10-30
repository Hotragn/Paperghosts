"""IIIF crops of article clippings from the Library of Congress page scans."""

import re

IIIF = "https://tile.loc.gov/image-services/iiif"
BATCH_PATH = re.compile(
    r"/data/batches/(?P<batch>[^/]+)/data/(?P<lccn>[^/]+)/(?P<reel>[^/]+)"
    r"/(?P<issue>[^/]+)/(?P<seq>[^/.]+)\.jp2$"
)


def service_id(raw_data_loc: str) -> str:
    """The page's IIIF service, from the batch path AmericanStories records for its scan."""
    path = BATCH_PATH.search(raw_data_loc)
    if path is None:
        raise ValueError("raw_data_loc is not a Chronicling America batch path")
    awardee = path["batch"].split("_")[0]
    return (
        f"service:ndnp:{awardee}:batch_{path['batch']}:data:"
        f"{path['lccn']}:{path['reel']}:{path['issue']}:{path['seq']}"
    )


def crop_url(service: str, boxes: list[dict]) -> str:
    """One crop covering every box, in the scan's own pixels, at half size."""
    x0, y0 = min(b["x0"] for b in boxes), min(b["y0"] for b in boxes)
    x1, y1 = max(b["x1"] for b in boxes), max(b["y1"] for b in boxes)
    return f"{IIIF}/{service}/{x0},{y0},{x1 - x0},{y1 - y0}/pct:50/0/default.jpg"
