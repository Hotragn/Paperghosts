"""Crop URLs name the scan's IIIF service, from its batch path or from loc.gov, and there is
one crop per box of an article, in reading order. Requests to the Library of Congress go
at most one a second and name the project, and each crop is fetched once and cached."""

import httpx
import pytest

from paperghosts.ingest import crops
from paperghosts.ingest.crops import (
    crop,
    crop_urls,
    crops_for,
    page_service,
    service_id,
)

# the Litchfield enquirer, 1850-04-25, as AmericanStories records its scan
RAW_DATA_LOC = (
    "https://chroniclingamerica.loc.gov/data/batches/ct_barnum_ver01/data/sn84020071"
    "/00414182975/1850042501/0199.jp2"
)
SERVICE = (
    "service:ndnp:ct:batch_ct_barnum_ver01:data:sn84020071:00414182975:1850042501:0199"
)
# the Lewistown gazette's 1850-07-26 knockings, whose scan has no batch path
LEWISTOWN = "faro_1850/1850-07-26_p1_sn83032276_00296028587_1850072601_0265.json"
LEWISTOWN_SERVICE = (
    "service:ndnp:pst:batch_pst_intramural_ver01:data:sn83032276:00296028587"
    ":1850072601:0265"
)


@pytest.fixture
def loc(monkeypatch):
    """Stands in for loc.gov and tile.loc.gov, and records every request."""
    requests, responses = [], {}

    def answer(request):
        requests.append(request)
        response = responses.get(request.url.path, httpx.Response(404))
        # a list is answered in turn; an exception in it is raised, as a dropped connection
        response = response.pop(0) if isinstance(response, list) else response
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(
        crops, "CLIENT", httpx.Client(transport=httpx.MockTransport(answer))
    )
    monkeypatch.setattr(crops, "sleep", lambda seconds: None)
    return requests, responses


def test_service_id_comes_from_the_batch_path():
    assert service_id(RAW_DATA_LOC) == SERVICE


def test_each_box_gets_its_own_crop_in_reading_order():
    # masthead line, headline, then the body; bbox_list is in the order its text is read
    boxes = [
        {"x0": 4886, "y0": 1300, "x1": 5818, "y1": 1398},
        {"x0": 5039, "y0": 1467, "x1": 5735, "y1": 1530},
        {"x0": 4913, "y0": 1543, "x1": 5867, "y1": 4903},
    ]
    base = f"https://tile.loc.gov/image-services/iiif/{SERVICE}"
    assert crop_urls(SERVICE, boxes) == [
        f"{base}/4886,1300,932,98/pct:50/0/default.jpg",
        f"{base}/5039,1467,696,63/pct:50/0/default.jpg",
        f"{base}/4913,1543,954,3360/pct:50/0/default.jpg",
    ]


def test_crops_keep_bbox_list_order_where_a_later_box_starts_higher():
    # "From the Detroit Advertiser." (1850): the body's box starts above the second
    # headline line's, and is read after it
    boxes = [
        {"x0": 397, "y0": 1752, "x1": 944, "y1": 1857},
        {"x0": 315, "y0": 1867, "x1": 1026, "y1": 1949},
        {"x0": 342, "y0": 1828, "x1": 1009, "y1": 6317},
    ]
    regions = [url.split("/")[-4] for url in crop_urls(SERVICE, boxes)]
    assert regions == ["397,1752,547,105", "315,1867,711,82", "342,1828,667,4489"]


def test_a_scan_without_a_batch_path_asks_loc_gov_which_batch_holds_it(loc):
    requests, responses = loc
    responses["/item/sn83032276/1850-07-26/ed-1/"] = httpx.Response(
        200, text=f'{{"page": [{{"image_url": "{LEWISTOWN_SERVICE}/full"}}]}}'
    )

    assert page_service(LEWISTOWN, {"height": 8352, "width": 5867}) == LEWISTOWN_SERVICE
    [request] = requests
    assert request.url.params["fo"] == "json"
    assert "PaperGhosts" in request.headers["user-agent"]


def test_a_page_loc_gov_has_no_item_for_is_a_lookup_failure(loc):
    # the Arizona tribune of 1964-11-06: AmericanStories has it, loc.gov answers 404
    with pytest.raises(LookupError):
        page_service(
            "faro_1964/1964-11-06_p1_sn84021918_0041421695A_1964110601_0620.json",
            {"height": 9000, "width": 7000},
        )


def test_requests_to_the_library_of_congress_go_at_most_one_a_second(loc, monkeypatch):
    requests, responses = loc
    responses["/a"] = responses["/b"] = httpx.Response(200)
    clock, waits = [500.0], []

    def sleep(seconds):
        waits.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(crops, "monotonic", lambda: clock[0])
    monkeypatch.setattr(crops, "sleep", sleep)
    monkeypatch.setattr(crops, "last_request", 0.0)

    crops.get("https://tile.loc.gov/a")
    clock[0] += 0.25
    crops.get("https://tile.loc.gov/b")

    assert waits == [0.0, 0.75] and len(requests) == 2


def test_loc_gov_json_requests_go_at_most_twenty_a_minute(loc, monkeypatch):
    # loc.gov's JSON API allows 20 a minute and blocks for an hour past that, and a probe
    # at one a second was blocked after about 20; its image services allow 150 a minute
    requests, responses = loc
    responses["/item/a/"] = responses["/item/b/"] = httpx.Response(200)
    clock, waits = [500.0], []

    def sleep(seconds):
        waits.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(crops, "monotonic", lambda: clock[0])
    monkeypatch.setattr(crops, "sleep", sleep)
    monkeypatch.setattr(crops, "last_request", 0.0)

    crops.get("https://www.loc.gov/item/a/", fo="json")
    clock[0] += 0.25
    crops.get("https://www.loc.gov/item/b/", fo="json")

    assert waits == [0.0, 3.25] and len(requests) == 2


@pytest.mark.parametrize(
    "busy",
    [httpx.Response(503), httpx.ConnectError("the connection dropped")],
    ids=["503", "dropped connection"],
)
def test_a_busy_server_is_asked_again_after_a_pause(loc, monkeypatch, busy):
    # tile.loc.gov answered a crop it hadn't made yet with a 503 after 35 s, and the same
    # URL a minute later in 0.2 s
    requests, responses = loc
    responses["/busy"] = [busy, httpx.Response(200, content=b"ok")]
    waits = []
    monkeypatch.setattr(crops, "sleep", waits.append)

    assert crops.get("https://tile.loc.gov/busy").content == b"ok"
    assert len(requests) == 2 and 5 in waits


def test_a_crop_is_fetched_once_and_then_read_from_the_cache(
    loc, monkeypatch, tmp_path
):
    requests, responses = loc
    monkeypatch.setattr(crops, "CROPS", tmp_path)
    url = f"https://tile.loc.gov/image-services/iiif/{SERVICE}/1,2,3,4/pct:50/0/default.jpg"
    responses[httpx.URL(url).path] = httpx.Response(
        200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"}
    )

    first, again = crop(url), crop(url)

    assert first == again and first.read_bytes() == b"\xff\xd8jpeg"
    assert len(requests) == 1 and [p.name for p in tmp_path.iterdir()] == [first.name]


def test_a_reissued_batch_is_found_through_loc_gov(loc, monkeypatch, tmp_path):
    # the Potowmac guardian, 1796-09-22: AmericanStories names the batch wvu_zarley_ver01,
    # which tile.loc.gov no longer serves, and loc.gov lists the page under ver02
    _, responses = loc
    monkeypatch.setattr(crops, "CROPS", tmp_path)
    member = "faro_1796/1796-09-22_p4_sn84038410_01000424529_1796092201_0172.json"
    scan = {
        "raw_data_loc": "https://chroniclingamerica.loc.gov/data/batches/wvu_zarley_ver01"
        "/data/sn84038410/01000424529/1796092201/0172.jp2"
    }
    ver02 = (
        "service:ndnp:wvu:batch_wvu_zarley_ver02:data:sn84038410:01000424529"
        ":1796092201:0172"
    )
    responses["/item/sn84038410/1796-09-22/ed-1/"] = httpx.Response(200, text=ver02)
    box = {"x0": 1, "y0": 2, "x1": 4, "y1": 6}
    [url] = crop_urls(ver02, [box])
    responses[httpx.URL(url).path] = httpx.Response(
        200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"}
    )

    service, [path] = crops_for(member, scan, [box])

    assert service == ver02 and path.read_bytes() == b"\xff\xd8jpeg"


def test_a_page_that_is_not_an_image_is_never_cached(loc, monkeypatch, tmp_path):
    _, responses = loc
    monkeypatch.setattr(crops, "CROPS", tmp_path)
    url = "https://tile.loc.gov/image-services/iiif/service:busy/full/pct:50/0/default.jpg"
    responses[httpx.URL(url).path] = httpx.Response(
        200,
        text="<html>Too many requests</html>",
        headers={"content-type": "text/html"},
    )

    with pytest.raises(ValueError):
        crop(url)
    assert list(tmp_path.iterdir()) == []
