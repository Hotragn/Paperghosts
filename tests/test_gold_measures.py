"""What the frozen gold labels measure: reports per stratum against the draw's expectation, the
weighted report rate, the story-place rule against the labelled place_state, and E9 from the
grouping."""

import pytest
from gold_measures import by_stratum, e9, final, paper_state, story_state, weighted


def place(quote, value=None):
    return {"value": value or quote, "quote": quote}


def test_the_story_place_rule_reads_the_state_from_the_text_or_the_dateline():
    text = "A Dead Mans Ghost. CUMBERLAxD, Nd, May Am interest ing ghost story comes from the town of Sharpsburg, Md. About ten days ago"
    assert story_state(text, place("Sharpsburg, Md")) == "Maryland"
    assert story_state(text, place("the town of Sharpsburg")) == "Maryland"

    dated = "A HAUNTED FARMHOUSE MILFORD, Conn., June 3.-The family of Mr. John Hale"
    assert story_state(dated, place("the old farmhouse")) == "Connecticut"
    assert (
        story_state("PHILADELPHIA, Pa, Dec. 22.-That Rev. Dr.", place("St. John's"))
        == "Pennsylvania"
    )
    assert (
        story_state("Albia, Ia., Sept. 19.-Bailey Black", place("the jail")) == "Iowa"
    )

    # no state in the text: the paper's state is never taken
    assert story_state("NEW YORK, Nov. 30.-The story of the", place("Brooklyn")) is None
    assert (
        story_state(
            "Saw Ghosts. correspondent writing from Hilo", place("writing from Hilo")
        )
        is None
    )
    assert (
        story_state(
            "la pri- son de Washington. Tellc est", place("la pri- son de Washington")
        )
        is None
    )
    assert (
        story_state("Buffalo, New York, Jan. 3", place("Buffalo, New York"))
        == "New York"
    )


def test_the_paper_state_is_the_printed_one_or_a_cached_records(tmp_path):
    assert (
        paper_state(
            {"paper": "Burlington free press. [volume] (Burlington, Vt.) 1827-1865"},
            tmp_path,
        )
        == "Vermont"
    )
    assert (
        paper_state(
            {
                "paper": "The herald.",
                "article_id": "79_1897-04-18_p2_sn85042461_0028.json",
            },
            tmp_path,
        )
        is None
    )
    (tmp_path / "sn85042461.json").write_text(
        '{"status": 200, "body": {"item": {"location_str": "Los Angeles, California", "location_state": ["california"]}}}'
    )
    assert (
        paper_state(
            {
                "paper": "The herald.",
                "article_id": "79_1897-04-18_p2_sn85042461_0028.json",
            },
            tmp_path,
        )
        == "California"
    )


def test_the_final_label_is_the_ruling_where_there_is_one():
    records = [
        {"article_id": "a", "labeller": "Claude", "kind": "idiom"},
        {"article_id": "a", "labeller": "second pass", "kind": "other"},
        {"article_id": "a", "labeller": "ruling", "kind": "other"},
        {"article_id": "b", "labeller": "Claude", "kind": "report"},
        {"article_id": "b", "labeller": "second pass", "kind": "report"},
    ]
    assert {aid: r["kind"] for aid, r in final(records).items()} == {
        "a": "other",
        "b": "report",
    }


def test_reports_are_counted_by_stratum_beside_the_expectation_and_weighted():
    items = [
        {"article_id": "a", "stratum": "s1", "weight": 10.0},
        {"article_id": "b", "stratum": "s1", "weight": 10.0},
        {"article_id": "c", "stratum": "s2", "weight": 1000.0},
    ]
    kinds = {"a": "report", "b": "fiction", "c": "idiom"}
    expected = {
        "strata": {"s1": {"reports": [0.8, 0.2, 1.5]}, "s2": {"reports": None}},
        "total": [1.0, 0.3, 2.0],
    }

    rows = by_stratum(items, kinds, expected)
    assert rows["strata"]["s1"] == {
        "gold": 2,
        "reports": 1,
        "expected": [0.8, 0.2, 1.5],
    }
    assert rows["strata"]["s2"] == {"gold": 1, "reports": 0, "expected": None}
    assert rows["total"] == {"gold": 3, "reports": 1, "expected": [1.0, 0.3, 2.0]}

    rate = weighted(items, kinds)
    assert rate["rate"] == pytest.approx(10 / 1020)
    low, high = rate["interval"]
    assert 0 <= low <= rate["rate"] <= high


def test_e9_is_an_article_whose_group_has_another_member():
    frame = {"ids": ["a", "b", "c", "d"], "group": ["a", "a", "c", "d"]}
    assert e9(frame, ["a", "b", "c"]) == {"a", "b"}
