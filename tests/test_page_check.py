"""The page check's report: its headline numbers, counted from its rows."""

from page_check import summary


def row(truth, verdict, status=200, approximate=False, recorded=(10, 8), info=(10, 8)):
    return {
        "truth": truth,
        "verdict": verdict,
        "info_status": status,
        "approximate": approximate,
        "recorded_size": list(recorded),
        "info_size": list(info) if status == 200 else None,
    }


def test_the_summary_counts_false_accepts_and_false_rejects_from_the_rows():
    results = {
        "measure": [
            row("same page", None),
            row("same page", "no such page", status=404),
            row(
                "same page", "the article's words aren't in its boxes", approximate=True
            ),
            row("the frame beside it", "no such page", status=404),
            row("the frame beside it", "the article's words aren't in its boxes"),
            row("the frame beside it", "another size", info=(10, 9)),
        ],
        "reels": [
            {"picked": "a", "batches": {"a": {"status": 200}, "b": {"status": 404}}},
            {"picked": "a", "batches": {"a": {"status": 404}, "b": {"status": 200}}},
            {"picked": "a", "batches": {"a": {"status": 404}, "b": {"status": 404}}},
        ],
        "requests": [{"sent": 3}, {"sent": 4}],
    }

    found = summary(results, probes=2)

    assert found["false_accepts"]["hits"] == 0 and found["false_accepts"]["n"] == 3
    assert found["false_accepts_where_the_frame_exists"]["n"] == 2
    assert found["size_alone_accepts_where_the_frame_exists"]["hits"] == 1
    assert found["false_rejects_where_the_page_exists"] == {
        "hits": 1,
        "n": 2,
        "share": 0.5,
        "low": found["false_rejects_where_the_page_exists"]["low"],
        "high": found["false_rejects_where_the_page_exists"]["high"],
    }
    assert found["own_frames_no_longer_served"] == 1
    assert found["reels_first_pick_serves"]["hits"] == 1
    assert found["reels_some_batch_serves"]["hits"] == 2
    assert found["requests"] == 9
