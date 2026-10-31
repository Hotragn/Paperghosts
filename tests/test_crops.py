"""Crop URLs name the scan's IIIF service, from its batch path or from loc.gov, and there is
one crop per box of an article, in reading order. Requests to the Library of Congress go
at most one a second and name the project, and each crop is fetched once and cached."""

import httpx
import pytest

from paperghosts.ingest import crops, reels
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
def loc(monkeypatch, tmp_path_factory):
    """Stands in for loc.gov and tile.loc.gov, and records every request. Its answers are
    cached in a folder of their own, and the reel-to-batch map starts empty."""
    requests, responses = [], {}
    monkeypatch.setattr(crops, "CACHE", tmp_path_factory.mktemp("requests"))
    monkeypatch.setattr(crops, "COUNTS", crops.Counter())
    monkeypatch.setattr(reels, "load", dict)

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


def test_a_service_is_named_by_its_batch_lccn_reel_issue_and_frame():
    assert (
        crops.service(
            "ct_barnum_ver01", "sn84020071", "00414182975", "1850042501", "0199"
        )
        == SERVICE
    )


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

    with pytest.raises(crops.Busy):
        crop(url)
    assert list(tmp_path.iterdir()) == []


def test_a_captcha_page_is_busy_so_it_is_asked_again_after_a_pause(loc, monkeypatch):
    # loc.gov: under heavy load, "429 status codes or HTML pages with CAPTCHAs" even below
    # its rates (Working Within Limits, read 2026-10-30)
    requests, responses = loc
    captcha = httpx.Response(
        200, text="<html>captcha</html>", headers={"content-type": "text/html"}
    )
    responses["/item/a/"] = [captcha, httpx.Response(200, json={"item": 1})]
    waits = []
    monkeypatch.setattr(crops, "sleep", waits.append)

    assert crops.get("https://www.loc.gov/item/a/", fo="json").json() == {"item": 1}
    assert len(requests) == 2 and 5 in waits


def test_a_captcha_page_is_never_cached(loc):
    requests, responses = loc
    responses["/item/a/"] = httpx.Response(
        200, text="<html>captcha</html>", headers={"content-type": "text/html"}
    )

    assert crops.cached("https://www.loc.gov/item/a/", fo="json")["status"] == "busy"
    crops.cached("https://www.loc.gov/item/a/", fo="json")

    assert len(requests) == 6 and crops.COUNTS["errors"] == 2


def test_a_404_is_an_answer_whatever_its_body(loc):
    requests, responses = loc
    responses["/item/gone/"] = httpx.Response(
        404, text="<html>not found</html>", headers={"content-type": "text/html"}
    )

    assert crops.cached("https://www.loc.gov/item/gone/", fo="json")["status"] == 404
    assert crops.cached("https://www.loc.gov/item/gone/", fo="json")["status"] == 404
    assert len(requests) == 1


def test_a_request_is_asked_once_and_cached_with_its_url_date_and_status(loc):
    requests, responses = loc
    responses["/item/a/"] = httpx.Response(200, json={"item": 1})

    first = crops.cached("https://www.loc.gov/item/a/", fo="json")
    again = crops.cached("https://www.loc.gov/item/a/", fo="json")

    assert len(requests) == 1 and first == again
    assert first["url"] == "https://www.loc.gov/item/a/?fo=json"
    assert first["status"] == 200 and first["body"] == {"item": 1}
    assert first["retrieved"].startswith("20")
    assert crops.COUNTS == {"requests": 1, "cache_hits": 1}


def test_a_404_is_cached_and_a_server_error_is_not_so_a_later_run_asks_again(loc):
    requests, responses = loc
    responses["/gone"] = httpx.Response(404)
    responses["/down"] = httpx.Response(503)

    assert crops.cached("https://tile.loc.gov/gone")["status"] == 404
    assert crops.cached("https://tile.loc.gov/gone")["body"] is None
    assert crops.cached("https://tile.loc.gov/down")["status"] == 503
    crops.cached("https://tile.loc.gov/down")

    asked = [r.url.path for r in requests]
    # get asks a busy server three times before it gives up
    assert asked.count("/gone") == 1 and asked.count("/down") == 6
    assert crops.COUNTS == {"requests": 3, "cache_hits": 1, "errors": 2}


def test_a_pages_ocr_is_the_alto_loc_keeps_beside_its_image():
    assert crops.alto_url(SERVICE) == (
        "https://tile.loc.gov/storage-services/service/ndnp/ct/batch_ct_barnum_ver01"
        "/data/sn84020071/00414182975/1850042501/0199.xml"
    )


def test_the_alto_kept_is_the_pages_size_and_each_word_with_its_box():
    # the Litchfield enquirer's ALTO, 1850-04-25, cut to its first three words
    alto = (
        '<alto><Layout><Page ID="PAGE1" HEIGHT="29656" WIDTH="20352" PC="0.79">'
        '<String ID="S1" CONTENT="THE" WC="1" HEIGHT="153" WIDTH="449" HPOS="1160"'
        ' VPOS="972"/><SP/><String ID="S2" CONTENT="ELECTION." HEIGHT="157" WIDTH="1125"'
        ' HPOS="1716" VPOS="972"/><String ID="S3" CONTENT="Smith &amp; Co" HEIGHT="133"'
        ' WIDTH="461" HPOS="1048" VPOS="1352"/></Page></Layout></alto>'
    )

    assert crops.alto_words(httpx.Response(200, text=alto)) == {
        "page": [20352, 29656],
        "words": [
            [1160, 972, 449, 153, "THE"],
            [1716, 972, 1125, 157, "ELECTION."],
            [1048, 1352, 461, 133, "Smith & Co"],
        ],
    }


def test_a_page_with_no_batch_path_gets_its_service_from_its_reels_batch(
    loc, monkeypatch
):
    requests, _ = loc
    reel_map = {"sn83032276": {"00296028587": {"pst_intramural_ver01": ["1850071901"]}}}
    monkeypatch.setattr(reels, "load", lambda: reel_map)

    assert page_service(LEWISTOWN, {"height": 8352, "width": 5867}) == LEWISTOWN_SERVICE
    assert requests == []


def test_an_issue_is_asked_of_loc_gov_once_for_all_its_pages(loc):
    requests, responses = loc
    next_frame = LEWISTOWN_SERVICE.replace(":0265", ":0266")
    responses["/item/sn83032276/1850-07-26/ed-1/"] = httpx.Response(
        200,
        text=f'{{"page": [{{"image_url": "{LEWISTOWN_SERVICE}/full"}},'
        f' {{"image_url": "{next_frame}/full"}}]}}',
    )

    assert page_service(LEWISTOWN, {}) == LEWISTOWN_SERVICE
    assert page_service(LEWISTOWN.replace("_0265.", "_0266."), {}) == next_frame
    assert len(requests) == 1


ARTICLE = (
    "The spectre appeared nightly beside the cemetery gates, frightening travellers,"
    " horses, watchmen, neighbours and several respectable citizens."
)
MARKET = (
    "Wheat prices advanced sharply yesterday, while cotton, barley, coffee, sugar,"
    " leather and copper closed steady at the exchange."
)
BOX = {"x0": 100, "y0": 100, "x1": 600, "y1": 400}  # in the scan's pixels


def a_page(responses, size=(1000, 800), words=ARTICLE):
    """info.json for LEWISTOWN_SERVICE's page, and its ALTO with these words laid out
    inside BOX, in ALTO's units: four to a pixel, as at 300 dpi."""
    height, width = size
    responses[f"/image-services/iiif/{LEWISTOWN_SERVICE}/info.json"] = httpx.Response(
        200, json={"height": height, "width": width}
    )
    strings = "".join(
        f'<String CONTENT="{word}" HPOS="{4 * (110 + 40 * (i % 10))}"'
        f' VPOS="{4 * (110 + 30 * (i // 10))}" WIDTH="120" HEIGHT="80"/>'
        for i, word in enumerate(words.split())
    )
    responses[httpx.URL(crops.alto_url(LEWISTOWN_SERVICE)).path] = httpx.Response(
        200,
        text=f'<alto><Page HEIGHT="{4 * height}" WIDTH="{4 * width}">{strings}</Page></alto>',
    )


def test_the_page_check_accepts_a_page_of_the_scans_size_with_the_article_in_its_boxes(
    loc,
):
    _, responses = loc
    a_page(responses)

    scan = {"height": 1000, "width": 800}
    assert crops.page_check(LEWISTOWN_SERVICE, scan, [BOX], ARTICLE) is None


def test_the_page_check_rejects_a_page_that_isnt_there(loc):
    assert (
        crops.page_check(LEWISTOWN_SERVICE, {"height": 1, "width": 1}, [BOX], ARTICLE)
        == "no such page"
    )


def test_the_page_check_rejects_a_page_of_another_size_without_reading_its_ocr(loc):
    requests, responses = loc
    a_page(responses, size=(1000, 812))

    scan = {"height": 1000, "width": 800}
    assert crops.page_check(LEWISTOWN_SERVICE, scan, [BOX], ARTICLE) == "another size"
    assert len(requests) == 1


def test_the_page_check_rejects_a_page_of_the_same_size_with_other_words_in_the_boxes(
    loc,
):
    # neighbouring frames of one issue can share a size
    _, responses = loc
    a_page(responses, words=MARKET)

    scan = {"height": 1000, "width": 800}
    assert crops.page_check(LEWISTOWN_SERVICE, scan, [BOX], ARTICLE) == (
        "the article's words aren't in its boxes"
    )


def test_a_page_of_approximate_size_must_hold_the_boxes_and_the_articles_words(loc):
    # an approximate size is only the extent of the boxes (decision 18)
    _, responses = loc
    a_page(responses)
    approximate = {"height": 400, "width": 600, "dimensions_approx": True}

    assert crops.page_check(LEWISTOWN_SERVICE, approximate, [BOX], ARTICLE) is None
    off = BOX | {"x1": 900}
    assert crops.page_check(LEWISTOWN_SERVICE, approximate, [off], ARTICLE) == (
        "boxes off the page"
    )


def test_an_article_of_few_words_cant_be_checked_by_them(loc):
    _, responses = loc
    a_page(responses)

    scan = {"height": 1000, "width": 800}
    assert crops.page_check(
        LEWISTOWN_SERVICE, scan, [BOX], "Spectre seen nightly."
    ) == ("too few words to check")


def test_a_page_with_no_batch_path_is_checked_before_any_crop_is_fetched(
    loc, monkeypatch, tmp_path
):
    _, responses = loc
    monkeypatch.setattr(crops, "CROPS", tmp_path)
    reel_map = {"sn83032276": {"00296028587": {"pst_intramural_ver01": ["1850071901"]}}}
    monkeypatch.setattr(reels, "load", lambda: reel_map)
    a_page(responses, words=MARKET)

    with pytest.raises(LookupError, match="words"):
        crops_for(LEWISTOWN, {"height": 1000, "width": 800}, [BOX], text=ARTICLE)
    assert list(tmp_path.iterdir()) == []


def test_where_the_maps_batch_doesnt_hold_the_page_loc_gov_names_it(
    loc, monkeypatch, tmp_path
):
    _, responses = loc
    monkeypatch.setattr(crops, "CROPS", tmp_path)
    reel_map = {"sn83032276": {"00296028587": {"pst_other_ver01": ["1850071901"]}}}
    monkeypatch.setattr(reels, "load", lambda: reel_map)
    responses["/item/sn83032276/1850-07-26/ed-1/"] = httpx.Response(
        200, text=LEWISTOWN_SERVICE
    )
    a_page(responses)
    [url] = crop_urls(LEWISTOWN_SERVICE, [BOX])
    responses[httpx.URL(url).path] = httpx.Response(
        200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"}
    )

    service, [path] = crops_for(
        LEWISTOWN, {"height": 1000, "width": 800}, [BOX], text=ARTICLE
    )

    assert service == LEWISTOWN_SERVICE and path.read_bytes() == b"\xff\xd8jpeg"


def test_where_the_maps_first_batch_doesnt_hold_the_page_its_next_does(
    loc, monkeypatch, tmp_path
):
    # ohi_dearfield and cohi_dearfield alternate along one reel, and only cohi_ serves this
    # page: the reel's next batch is tried before loc.gov is asked
    requests, responses = loc
    monkeypatch.setattr(crops, "CROPS", tmp_path)
    reel_map = {
        "sn83032276": {
            "00296028587": {
                "pst_other_ver01": ["1850072601"],
                "pst_intramural_ver01": ["1850080201"],
            }
        }
    }
    monkeypatch.setattr(reels, "load", lambda: reel_map)
    a_page(responses)
    [url] = crop_urls(LEWISTOWN_SERVICE, [BOX])
    responses[httpx.URL(url).path] = httpx.Response(
        200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"}
    )

    service, _ = crops_for(
        LEWISTOWN, {"height": 1000, "width": 800}, [BOX], text=ARTICLE
    )

    assert service == LEWISTOWN_SERVICE
    assert not any(r.url.host == "www.loc.gov" for r in requests)


def test_a_page_whose_member_names_another_frame_takes_the_members_and_is_checked(
    loc, monkeypatch, tmp_path
):
    # its batch path names frame 0264, and the member 0265, the article's page
    _, responses = loc
    monkeypatch.setattr(crops, "CROPS", tmp_path)
    scan = {
        "height": 1000,
        "width": 800,
        "raw_data_loc": "https://chroniclingamerica.loc.gov/data/batches"
        "/pst_intramural_ver01/data/sn83032276/00296028587/1850072601/0264.jp2",
    }
    assert page_service(LEWISTOWN, scan) == LEWISTOWN_SERVICE
    a_page(responses, words=MARKET)

    with pytest.raises(LookupError, match="words"):
        crops_for(LEWISTOWN, scan, [BOX], text=ARTICLE)
    assert list(tmp_path.iterdir()) == []


def test_a_page_whose_member_and_batch_path_agree_is_shown_unchecked(
    loc, monkeypatch, tmp_path
):
    requests, responses = loc
    monkeypatch.setattr(crops, "CROPS", tmp_path)
    [url] = crop_urls(SERVICE, [BOX])
    responses[httpx.URL(url).path] = httpx.Response(
        200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"}
    )
    member = "faro_1850/1850-04-25_p1_sn84020071_00414182975_1850042501_0199.json"

    service, _ = crops_for(member, {"raw_data_loc": RAW_DATA_LOC}, [BOX])

    assert service == SERVICE
    assert [r.url.path.endswith("default.jpg") for r in requests] == [True]
