"""IIIF crops of article clippings from the Library of Congress page scans, and the cache
under data/crops/ that keeps each crop once it is fetched. Other answers from the Library of
Congress are cached under data/loc/requests/, each with its URL, date and status."""

import hashlib
import html
import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep

import httpx

from paperghosts.ingest import reels

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
ALTO = "https://tile.loc.gov/storage-services/service/ndnp/{}/{}/data/{}/{}/{}/{}.xml"
ALTO_PAGE = re.compile(r"<Page\s([^>]*)>")
ALTO_STRING = re.compile(r"<String\s([^>]*?)/?>")
ATTRIBUTE = re.compile(r'(\w+)="([^"]*)"')
LISTED = re.compile(r"service:ndnp:[a-z]+:batch_\w+?:data:\w+:\w+:\d{10}:\d+")
CROPS = Path(__file__).parents[2] / "data" / "crops"
NO_SUCH_PAGE = "no such page"
# the page check's text rule (decision 35), chosen on calibration's 38 pages: the article's
# words inside its boxes were 0.31 to 1.0 on its page and 0 to 0.11 on the frame beside it
SHARE, FEWEST_WORDS = 0.2, 10
CACHE = Path(__file__).parents[2] / "data" / "loc" / "requests"
COUNTS = (
    Counter()
)  # requests to the Library of Congress, cache hits, and errors not cached
SENT = Counter()  # requests sent, by host, each of get's tries counted
USER_AGENT = (
    "PaperGhosts/0.1 (a Hacktoberfest ghost-story map; github.com/Hotragn/Paperghosts)"
)
CLIENT = httpx.Client(timeout=60, follow_redirects=True)
last_request = 0.0  # monotonic time of the last request to the Library of Congress
BUSY = {429, 500, 502, 503, 504, 520, 521, 522, 523, 524}  # 52x: Cloudflare's
# seconds between requests: loc.gov's JSON API allows 20 a minute and blocks for an hour past
# that, and its image services allow 150 a minute
GAPS = {"www.loc.gov": 3.5}


def service(batch: str, lccn: str, reel: str, issue: str, seq: str) -> str:
    """A page's IIIF service, named by its batch and its place in the batch."""
    awardee = batch.split("_")[0]
    return f"service:ndnp:{awardee}:batch_{batch}:data:{lccn}:{reel}:{issue}:{seq}"


def service_id(raw_data_loc: str) -> str:
    """The page's IIIF service, from the batch path AmericanStories records for its scan."""
    path = BATCH_PATH.search(raw_data_loc)
    if path is None:
        raise ValueError("raw_data_loc is not a Chronicling America batch path")
    return service(**path.groupdict())


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
    """A GET to the Library of Congress: at most one a second, or one in 3.5 s to loc.gov's
    JSON API, naming the project, and asked again after a pause while the server is busy.
    tile.loc.gov can answer a crop it hasn't made yet with a 503."""
    global last_request
    gap = GAPS.get(httpx.URL(url).host, 1.0)
    for pause in (5, 20, None):
        sleep(max(0.0, last_request + gap - monotonic()))
        last_request = monotonic()
        SENT[httpx.URL(url).host] += 1
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


def cached(
    url: str, keep=lambda response: response.json(), path=None, counts=None, **params
) -> dict:
    """A GET to the Library of Congress, asked for once: the record of its url, the date it
    was retrieved, its status and what `keep` takes from its body. A 404 is cached too, so it
    isn't asked for twice either. A server error still failing after get's retries isn't, so a
    later run asks again."""
    counts = COUNTS if counts is None else counts
    asked = str(httpx.URL(url, params=params))
    path = path or CACHE / f"{hashlib.sha256(asked.encode()).hexdigest()[:24]}.json"
    if path.exists():
        counts["cache_hits"] += 1
        return json.loads(path.read_text())
    counts["requests"] += 1
    try:
        response = get(url, **params)
        status, body = response.status_code, keep(response)
    except httpx.HTTPStatusError as exc:
        status, body = exc.response.status_code, None
        if status != 404 and status < 500:
            raise
    record = {
        "url": asked,
        "retrieved": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": status,
        "body": body,
    }
    if status >= 500:
        counts["errors"] += 1
        return record
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.{os.getpid()}.partial")
    partial.write_text(json.dumps(record))
    partial.replace(path)
    return record


def services_listed(response) -> list:
    """What the cache keeps of a loc.gov issue: the IIIF services of all its pages."""
    return sorted(set(LISTED.findall(response.text)))


def listed(lccn: str, reel: str, issue: str, seq: str) -> str:
    """The page's IIIF service as the loc.gov item for its issue lists it (decision 18). The
    item is asked for once and cached, so the issue's other pages are found without asking."""
    url = f"https://www.loc.gov/item/{lccn}/{issue[:4]}-{issue[4:6]}-{issue[6:8]}/ed-{int(issue[8:])}/"
    record = cached(url, keep=services_listed, fo="json")
    if record["status"] == 404:
        raise LookupError(f"loc.gov has no item for {lccn} {issue}")
    if record["status"] != 200:  # not cached, so a later call asks again
        raise LookupError(f"loc.gov answered {record['status']} for {lccn} {issue}")
    page = f":data:{lccn}:{reel}:{issue}:{seq}"
    for found in record["body"]:
        if found.endswith(page):
            return found
    raise LookupError(f"loc.gov lists no IIIF service for {lccn} {reel} {issue} {seq}")


def page_service(member: str, scan: dict) -> str:
    """The page's IIIF service: from its batch path; or else from its reel's batch in the
    reel-to-batch map (decision 35); or else from the loc.gov item that lists the page. A
    page with no batch path is unchecked here: crops_for checks it before any crop is
    fetched."""
    if scan.get("raw_data_loc"):
        return service_id(scan["raw_data_loc"])
    page = MEMBER.search(member)
    if page is None:
        raise LookupError(f"{member} is not a faro page name")
    found = mapped(member)
    return (
        found[0]
        if found
        else listed(page["lccn"], page["reel"], page["issue"], page["seq"])
    )


def mapped(member: str) -> list[str]:
    """The services the reel-to-batch map gives a page with no batch path, in the order to
    try them (reels.ranked); none where the map doesn't hold its reel."""
    page = MEMBER.search(member)
    batches = reels.load().get(page["lccn"], {}).get(page["reel"])
    if not batches:
        return []
    where = (page["lccn"], page["reel"], page["issue"], page["seq"])
    return [service(b, *where) for b in reels.ranked(batches, page["issue"])]


def alto_url(service: str) -> str:
    """The page's OCR, as ALTO XML, which LoC keeps beside its image."""
    _, _, awardee, batch, _, *page = service.split(":")
    return ALTO.format(awardee, batch, *page)


def alto_words(response) -> dict:
    """What the page check keeps of a page's ALTO: the page's size in ALTO's units (1/1200 of
    an inch), and each word with its box in them, in reading order."""
    page = dict(ATTRIBUTE.findall(ALTO_PAGE.search(response.text)[1]))
    words = []
    for found in ALTO_STRING.finditer(response.text):
        word = dict(ATTRIBUTE.findall(found[1]))
        box = [word.get(k) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")]
        if None not in box and "CONTENT" in word:
            words.append(
                [round(float(v)) for v in box] + [html.unescape(word["CONTENT"])]
            )
    return {
        "page": [round(float(page["WIDTH"])), round(float(page["HEIGHT"]))],
        "words": words,
    }


def words(text: str) -> set:
    """The distinct words of five letters or more that the page check compares."""
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 5}


def in_boxes(alto: dict, height: int, width: int, boxes: list[dict]) -> set:
    """The words of a page's ALTO whose centres lie inside the article's boxes, which are in
    the scan's pixels: height by width, as info.json gives them."""
    sx, sy = alto["page"][0] / width, alto["page"][1] / height
    return words(
        " ".join(
            word
            for x, y, w, h, word in alto["words"]
            if any(
                b["x0"] * sx <= x + w / 2 <= b["x1"] * sx
                and b["y0"] * sy <= y + h / 2 <= b["y1"] * sy
                for b in boxes
            )
        )
    )


def page_check(service: str, scan: dict, boxes: list[dict], text: str) -> str | None:
    """Why the page at service isn't the one the article was read from, or None where it is
    (decision 35). For a page located without a batch path, before its crop is shown:
    1. The page has to exist: info.json answers.
    2. It has to be the scan's size. Where AmericanStories marks the size approximate, which is
       only the extent of its boxes (decision 18), the boxes have to lie on the page.
    3. LoC's OCR of it has to hold the article's words inside the article's boxes: a fifth of
       its distinct words of five letters or more. Neighbouring frames can share a size."""
    info = cached(f"{IIIF}/{service}/info.json")
    if info["status"] == 404:
        return NO_SUCH_PAGE
    if info["status"] != 200:  # not cached, so a later check asks again
        raise LookupError(f"tile.loc.gov answered {info['status']} for {service}")
    height, width = info["body"]["height"], info["body"]["width"]
    if scan.get("dimensions_approx"):
        if any(b["x1"] > width or b["y1"] > height for b in boxes):
            return "boxes off the page"
    elif (scan.get("height"), scan.get("width")) != (height, width):
        return "another size"
    wanted = words(text or "")
    if len(wanted) < FEWEST_WORDS:
        return "too few words to check"
    alto = cached(alto_url(service), keep=alto_words)
    if alto["status"] == 404:
        return "no OCR to check"
    if alto["status"] != 200:
        raise LookupError(f"tile.loc.gov answered {alto['status']} for its OCR")
    if len(wanted & in_boxes(alto["body"], height, width, boxes)) < SHARE * len(wanted):
        return "the article's words aren't in its boxes"
    return None


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


def crops_for(
    member: str,
    scan: dict,
    boxes: list[dict],
    service: str | None = None,
    text: str | None = None,
):
    """The page's IIIF service and its crops, one per box.
    - A page with no batch path is checked against its article's text before any crop is
      fetched (page_check). Its reel's batches are tried in turn, and where none of them
      holds the page, loc.gov names its batch, and that page is checked too.
    - A batch path can name a batch that LoC has since reissued (ver01 where it now serves
      ver02), so when a crop from it is missing, loc.gov names the page's current service."""
    page = MEMBER.search(member)
    where = (page["lccn"], page["reel"], page["issue"], page["seq"])
    if not scan.get("raw_data_loc"):
        reasons = []
        for trial in [service] if service else mapped(member):
            why = page_check(trial, scan, boxes, text)
            if why is None:
                service = trial
                break
            reasons.append(why)
        else:
            held = [why for why in reasons if why != NO_SUCH_PAGE]
            if held:
                raise LookupError(f"{member}: {held[0]}")
            service = listed(*where)
            why = page_check(service, scan, boxes, text)
            if why:
                raise LookupError(f"{member}: {why}")
        return service, [crop(url) for url in crop_urls(service, boxes)]
    service = service or page_service(member, scan)
    try:
        return service, [crop(url) for url in crop_urls(service, boxes)]
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
    service = listed(*where)
    return service, [crop(url) for url in crop_urls(service, boxes)]
