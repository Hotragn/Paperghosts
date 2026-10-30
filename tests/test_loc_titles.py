"""loc.gov title records: one request each, cached with its URL and retrieval date, and a 404
cached too; and the place, state and title a record gives."""

from collections import Counter

import httpx

from paperghosts.geo import loc


class Answer:
    def __init__(self, status, body=None):
        self.status_code, self.body = status, body

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://www.loc.gov/")
            raise httpx.HTTPStatusError(
                "", request=request, response=httpx.Response(self.status_code)
            )


def test_a_record_is_asked_for_once_and_cached_with_its_url_and_date(
    tmp_path, monkeypatch
):
    asked = []

    def get(url, **params):
        asked.append(url)
        answer = Answer(200, {"item": {"location_str": "Phoenix, Arizona"}})
        answer.raise_for_status()
        return answer

    monkeypatch.setattr(loc, "get", get)
    monkeypatch.setattr(loc, "COUNTS", loc.Counter())

    first = loc.title_record("sn78001213", tmp_path)
    again = loc.title_record("sn78001213", tmp_path)

    assert asked == ["https://www.loc.gov/item/sn78001213/"]
    assert (
        first == again
        and first["url"] == "https://www.loc.gov/item/sn78001213/?fo=json"
    )
    assert first["status"] == 200 and first["retrieved"].startswith("20")
    assert loc.COUNTS == {"requests": 1, "cache_hits": 1}


def test_a_missing_record_is_cached_as_a_404(tmp_path, monkeypatch):
    def get(url, **params):
        Answer(404).raise_for_status()

    monkeypatch.setattr(loc, "get", get)
    monkeypatch.setattr(loc, "COUNTS", loc.Counter())

    assert loc.title_record("sn00000000", tmp_path)["status"] == 404
    assert loc.title_record("sn00000000", tmp_path)["body"] is None
    assert loc.COUNTS == {"requests": 1, "cache_hits": 1}


def test_a_server_error_is_counted_and_not_cached_so_a_later_run_asks_again(
    tmp_path, monkeypatch
):
    def get(url, **params):
        Answer(520).raise_for_status()

    monkeypatch.setattr(loc, "get", get)
    monkeypatch.setattr(loc, "COUNTS", loc.Counter())

    found = loc.title_record("sn83030273", tmp_path)

    assert found["status"] == 520 and found["body"] is None
    assert not list(tmp_path.iterdir())
    assert loc.COUNTS == {"requests": 1, "errors": 1}


def test_a_record_gives_its_place_state_county_title_and_years():
    record = {
        "status": 200,
        "body": {
            "item": {
                "location_str": "Tucson, Arizona",
                "location_county": ["santa cruz", "pima"],
                "title": "Weekly Arizonian (Tubac, Ariz.) 1859-1871",
                "dates_of_publication": "1859-1871",
            }
        },
    }

    # a paper that moved has both its counties, to check either printed place against
    assert loc.recorded(record) == {
        "place": "Tucson",
        "state": "Arizona",
        "county": "Santa Cruz",
        "counties": ["Santa Cruz", "Pima"],
        "title": "Weekly Arizonian (Tubac, Ariz.) 1859-1871",
        "years": "1859-1871",
    }
    assert loc.recorded({"status": 404, "body": None}) is None


def test_the_lookup_uses_a_cached_record_but_asks_only_for_a_paper_with_no_place(
    tmp_path, monkeypatch
):
    import titles  # scripts/titles.py

    record = {
        "url": "https://www.loc.gov/item/sn87057062/?fo=json",
        "retrieved": "2026-10-30T12:00:00+00:00",
        "status": 200,
        "body": {
            "item": {
                "location_str": "Muscatine, Iowa",
                "location_county": ["muscatine"],
            }
        },
    }
    (tmp_path / "sn87057062.json").write_text("{}")
    asked = []
    monkeypatch.setattr(loc, "CACHE", tmp_path)
    monkeypatch.setattr(
        loc, "title_record", lambda lccn, cache=None: asked.append(lccn) or record
    )
    states = Counter({"Iowa": 2})

    found = titles.entry(
        "sn87057062",
        Counter({"Muscatine journal. [volume] (Bloomington, Iowa) 1849-185?": 2}),
        states,
    )
    assert found["source"] == "title string" and found["place"] == "Bloomington"
    assert found["catalogued_place"] == "Muscatine"
    assert found["catalogued_county"] == "Muscatine"
    assert found["then_and_now"] == "Bloomington, Iowa (now Muscatine)"

    uncached = titles.entry(
        "sn84038114",
        Counter({"Iowa state gazette. (Burlington, Iowa) 1847-1848": 1}),
        states,
    )
    assert asked == ["sn87057062"] and "catalogued_place" not in uncached
