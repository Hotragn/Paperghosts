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
    holding = {"seance": 100, "ouija": 50, "spirit+medium": 400}
    alone = {"seance": 60, "ouija": 30, "spirit+medium": 400}

    rules = summarise_rules(sample, holding, alone, total=500)

    assert (rules["seance"]["count"], rules["seance"]["n"]) == (1, 2)
    assert rules["seance"]["implied"] == 50 and not rules["seance"]["no_report"]
    assert rules["ouija"]["no_report"] and rules["spirit+medium"]["no_report"]


def test_a_rules_marginal_yield_counts_only_the_reports_no_other_rule_catches():
    sample = [
        {"terms": ["seance"], "ghost_report": True},
        {"terms": ["seance", "spirit+medium"], "ghost_report": True},
        {"terms": ["spirit+medium"], "ghost_report": False},
        {"terms": ["spirit+medium"], "ghost_report": False},
    ]
    holding = {"seance": 100, "spirit+medium": 400}
    alone = {"seance": 60, "spirit+medium": 300}

    rules = summarise_rules(sample, holding, alone, total=460)

    # both rules catch the shared report, but only seance catches one alone
    seance, medium = rules["seance"], rules["spirit+medium"]
    assert (seance["marginal"]["count"], seance["marginal"]["n"]) == (1, 4)
    assert seance["marginal"]["implied"] == 115
    assert medium["marginal"]["count"] == 0 and medium["count"] == 1
    # and among the sampled articles holding no other rule
    assert (seance["only"]["count"], seance["only"]["n"]) == (1, 1)
    assert seance["only"]["implied"] == 60
    assert (medium["only"]["count"], medium["only"]["n"]) == (0, 2)


def test_recall_counts_the_reports_of_both_lexicons():
    v1 = {"implied_low": 10, "implied": 20, "implied_high": 40}
    gained = {"implied_low": 5, "implied": 10, "implied_high": 20}
    missed = {"implied": 10, "implied_high": 30}

    recall = recall_in_sample(v1, gained, missed)

    assert recall["point"] == 30 / 40
    assert recall["at_least"] == {"low": 15 / 45, "point": 30 / 60, "high": 60 / 90}
