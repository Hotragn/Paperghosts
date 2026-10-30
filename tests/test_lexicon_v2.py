"""Lexicon v2 against v1: v2 only adds candidates, each rule's share of the judged sample is
reported, and recall counts both lexicons' reports."""

from lexicon_v2 import compare, recall_in_sample, summarise_rules


def test_v2_keeps_every_v1_candidate_and_adds_only_new_terms():
    v1 = {"a", "b"}
    v2 = [
        {"article_id": "a", "terms": ["ghost"]},
        {"article_id": "c", "terms": ["seance"]},
        {"article_id": "d", "terms": ["ghost", "seance"]},
    ]

    found = compare(v1, v2, new={"seance"})

    assert found["missing"] == ["b"]
    assert [row["article_id"] for row in found["added"]] == ["c", "d"]
    # d holds an old term, so v1 should have made it a candidate
    assert found["old_terms"] == ["d"]


def test_a_rule_with_no_report_in_its_share_is_flagged():
    sample = [
        {"terms": ["seance"], "ghost_report": True},
        {"terms": ["seance", "ouija"], "ghost_report": False},
        {"terms": ["ouija"], "ghost_report": False},
        {"terms": ["spirit+medium"], "ghost_report": False},
    ]
    added = {"seance": 100, "ouija": 50, "spirit+medium": 400}

    rules = summarise_rules(sample, added)

    assert (rules["seance"]["count"], rules["seance"]["n"]) == (1, 2)
    assert rules["seance"]["implied"] == 50 and not rules["seance"]["no_report"]
    assert rules["ouija"]["no_report"] and rules["spirit+medium"]["no_report"]


def test_recall_counts_the_reports_of_both_lexicons():
    v1 = {"implied_low": 10, "implied": 20, "implied_high": 40}
    gained = {"implied_low": 5, "implied": 10, "implied_high": 20}
    missed = {"implied": 10, "implied_high": 30}

    recall = recall_in_sample(v1, gained, missed)

    assert recall["point"] == 30 / 40
    assert recall["at_least"] == {"low": 15 / 45, "point": 30 / 60, "high": 60 / 90}
