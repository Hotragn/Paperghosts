"""The crop check takes one candidate from each of 50 years spread across all of them, at
random with a fixed seed, and no more than two from one LoC batch. A candidate whose page
has no IIIF service stays in the picks as a failure."""

from collections import Counter

from crop_check import pick, spread

from paperghosts.ingest.crops import batch

YEARS = list(range(1800, 1900))


def load(year):
    return [{"article_id": f"{year}-{i}", "bbox_list": [{"x0": 0}]} for i in range(5)]


def resolve(row):
    # four of each year's five candidates share one batch; the fifth has its own
    year, i = map(int, row["article_id"].split("-"))
    name = "shared" if i < 4 else f"own{year}"
    return f"service:ndnp:xx:batch_{name}:data:sn0:0:0:0"


def test_the_picks_spread_across_the_years_and_take_at_most_two_from_a_batch():
    picks = pick(YEARS, load, resolve)

    years = spread(YEARS, 50)
    assert (years[0], years[-1], len(set(years))) == (1800, 1899, 50)
    assert [p["year"] for p in picks] == years
    taken = Counter(batch(p["service"]) for p in picks)
    assert taken["shared"] == 2 and max(taken.values()) == 2
    assert pick(YEARS, load, resolve) == picks  # the seed fixes them


def test_a_page_without_a_service_stays_in_as_a_failure():
    def lost(row):
        raise LookupError(f"loc.gov lists no IIIF service for {row['article_id']}")

    picks = pick(YEARS, load, lost)

    assert len(picks) == 50 and all(p["service"] is None for p in picks)
    assert picks[0]["error"].startswith("loc.gov lists no IIIF service")
