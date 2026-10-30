"""The year scan keeps ghost-term articles as candidates, and keeps seeded, fixed-size
reservoir samples of the near-miss pool and of all non-candidates."""

import random

from paperghosts.ingest.prefilter import Reservoir, scan


def test_reservoir_keeps_a_uniform_sample_of_fixed_size():
    first = last = 0
    for seed in range(1000):
        reservoir = Reservoir(5, random.Random(seed))
        for item in range(50):
            reservoir.offer(item)
        assert sorted(set(reservoir.items)) == sorted(reservoir.items)
        assert len(reservoir.items) == 5
        first += 0 in reservoir.items
        last += 49 in reservoir.items
    # each item should be kept about 100 times in 1,000; a biased reservoir lands far outside
    assert 70 <= first <= 130 and 70 <= last <= 130


def test_reservoir_keeps_everything_while_there_is_room():
    reservoir = Reservoir(5, random.Random(0))
    for item in range(3):
        reservoir.offer(item)
    assert reservoir.items == [0, 1, 2]


def page(*texts):
    return {
        "lccn": {"title": "The test herald.", "lccn": "sn0", "state": "Connecticut"},
        "edition": {"date": "1850-04-12"},
        "scan": {"width": 10, "height": 10},
        "full articles": [
            {"id": f"a{i}", "headline": "", "article": text, "bbox_list": []}
            for i, text in enumerate(texts)
        ],
    }


def test_scan_sorts_articles_into_candidates_and_samples():
    pages = [
        (
            "faro_1850/p0.json",
            page("A ghost was seen.", "Strange noises.", "Wheat is up."),
        )
    ]

    result = scan(pages, year=1850, sample_size=10)

    assert (result["pages"], result["articles"], result["near_miss"]) == (1, 3, 1)
    assert result["by_state"] == {
        "Connecticut": {"pages": 1, "articles": 3, "candidates": 1}
    }
    assert [c["article_id"] for c in result["candidates"]] == ["a0"]
    assert result["candidates"][0]["terms"] == {"ghost": ["ghost"]}
    assert [s["article_id"] for s in result["samples"]["near_miss"]] == ["a1"]
    assert sorted(s["article_id"] for s in result["samples"]["random"]) == ["a1", "a2"]
    assert result["only"] == {"ghost": 1}
