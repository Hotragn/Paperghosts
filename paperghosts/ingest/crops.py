"""IIIF crops of article clippings from the Library of Congress page scans, and the cache
under data/crops/ that keeps each crop once it is fetched."""

import hashlib
import os
import re
from pathlib import Path
from time import monotonic, sleep

import httpx

IIIF = "https://tile.loc.gov/image-services/iiif"
BATCH_PATH = re.compile(
    r"/data/batches/(?P<batch>[^/]+)/data/(?P<lccn>[^/]+)/(?P<reel>[^/]+)"
    r"/(?P<issue>[^/]+)/(?P<seq>[^/.]+)\.jp2$"
)
# a faro member: date, page, LCCN, reel (sometimes 'no_reel'), issue and sequence
MEMBER = re.compile(
    r"(?P<date>\d{4}-\d\d-\d\d)_p[^_]*_(?P<lccn>[^_]+)_(?P<reel>.+)"
    r"_(?P<issue>\d{10})_(?P<seq>\d+)(?:\.json)?$"
)
CROPS = Path(__file__).parents[2] / "data" / "crops"
USER_AGENT = (
    "PaperGhosts/0.1 (a Hacktoberfest ghost-story map; github.com/Hotragn/Paperghosts)"
)
CLIENT = httpx.Client(timeout=60, follow_redirects=True)
last_request = 0.0  # monotonic time of the last request to the Library of Congress
BUSY = {429, 500, 502, 503, 504}


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


def crop_urls(service: str, boxes: list[dict]) -> list[str]:
    """One crop per box, in the scan's own pixels at half size, in bbox_list's order, which
    is the order the article is read in. One crop over every box would take in the columns
    between them."""
    return [
        f"{IIIF}/{service}/{b['x0']},{b['y0']},{b['x1'] - b['x0']},{b['y1'] - b['y0']}"
        "/pct:50/0/default.jpg"
        for b in boxes
    ]


def get(url, **params):
    """A GET to the Library of Congress: at most one a second, naming the project, and asked
    again after a pause while the server is busy. tile.loc.gov can answer a crop it hasn't
    made yet with a 503."""
    global last_request
    for pause in (5, 20, None):
        sleep(max(0.0, last_request + 1 - monotonic()))
        last_request = monotonic()
        try:
            response = CLIENT.get(
                url, params=params, headers={"User-Agent": USER_AGENT}
            )
        except httpx.TransportError:
            if pause is None:
                raise
        else:
            if response.status_code not in BUSY or pause is None:
                response.raise_for_status()
                return response
        sleep(pause)


def page_service(member: str, scan: dict) -> str:
    """The page's IIIF service, from its batch path, or else from the loc.gov item that
    lists the page, since some scans have no batch path (decision 18)."""
    if scan.get("raw_data_loc"):
        return service_id(scan["raw_data_loc"])
    page = MEMBER.search(member)
    if page is None:
        raise LookupError(f"{member} is not a faro page name")
    url = f"https://www.loc.gov/item/{page['lccn']}/{page['date']}/ed-{int(page['issue'][-2:])}/"
    try:
        item = get(url, fo="json").text
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        raise LookupError(f"loc.gov has no item for {member}") from exc
    found = re.search(
        rf"service:ndnp:[a-z]+:batch_\w+?:data:{page['lccn']}:{page['reel']}"
        rf":{page['issue']}:{page['seq']}",
        item,
    )
    if found is None:
        raise LookupError(f"loc.gov lists no IIIF service for {member}")
    return found[0]


def batch(service: str) -> str:
    """The LoC batch that holds the page, from its IIIF service."""
    return re.search(r":batch_(\w+?):data:", service)[1]


def crop(url: str) -> Path:
    """The crop at url, from the cache, which is keyed by the URL, or fetched once into it."""
    path = CROPS / f"{hashlib.sha256(url.encode()).hexdigest()[:24]}.jpg"
    if not path.exists():
        response = get(url)
        if not response.headers.get("content-type", "").startswith("image/"):
            raise ValueError(f"tile.loc.gov sent no image for {url}")
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_name(f"{path.name}.{os.getpid()}.partial")
        partial.write_bytes(response.content)
        partial.replace(path)
    return path


def crops_for(member: str, scan: dict, boxes: list[dict], service: str | None = None):
    """The page's IIIF service and its crops, one per box. A batch path can name a batch
    that LoC has since reissued (ver01 where it now serves ver02), so when a crop from it is
    missing, loc.gov names the page's current service."""
    service = service or page_service(member, scan)
    try:
        return service, [crop(url) for url in crop_urls(service, boxes)]
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404 or not scan.get("raw_data_loc"):
            raise
    service = page_service(member, {})
    return service, [crop(url) for url in crop_urls(service, boxes)]
