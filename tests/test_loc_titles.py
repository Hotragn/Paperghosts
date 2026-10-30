"""loc.gov title records: one request each, cached with its URL and retrieval date, and a 404
cached too; and the place, state and title a record gives."""

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
                "location_str": "Phoenix, Arizona",
                "location_county": ["maricopa"],
                "title": "The Phoenix Jewish News (Phoenix) 1948-1983",
                "dates_of_publication": "1948-1983",
            }
        },
    }

    assert loc.recorded(record) == {
        "place": "Phoenix",
        "state": "Arizona",
        "county": "Maricopa",
        "title": "The Phoenix Jewish News (Phoenix) 1948-1983",
        "years": "1948-1983",
    }
    assert loc.recorded({"status": 404, "body": None}) is None
