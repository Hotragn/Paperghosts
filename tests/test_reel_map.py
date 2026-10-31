"""The reel-to-batch map's check: each issue hidden in turn, every page of it at once, and its
batch picked from the rest of its reel; and the candidates the map covers."""

from reel_map import check, coverage, frame_rule, held_out

REEL_MAP = {
    "sn1": {
        # a split reel; d holds a single issue, which only its own pages could name
        "r1": {
            "a_ver01": ["1850010101", "1850011501", "1850020101"],
            "b_ver01": ["1850060101", "1850060801"],
            "d_ver01": ["1850030101"],
        },
        # a reel with one issue, which can't be tested
        "r2": {"c_ver01": ["1850010101"]},
    }
}


def test_each_issue_is_picked_from_the_rest_of_its_reel_with_all_its_pages_hidden():
    picked = {
        issue: (truth, batch) for _, reel, issue, truth, batch in held_out(REEL_MAP)
    }

    assert picked["1850011501"] == ({"a_ver01"}, "a_ver01")
    assert picked["1850060101"] == ({"b_ver01"}, "b_ver01")
    # March is nearer a's February than b's June, and d's own issue is hidden
    assert picked["1850030101"] == ({"d_ver01"}, "a_ver01")
    assert [b for _, reel, _, _, b in held_out(REEL_MAP) if reel == "r2"] == [None]


def page(path, reel, issue, candidates=1):
    return {"path": path, "reel": reel, "issue": issue, "candidates": candidates}


def test_the_check_counts_hits_over_issues_overall_and_on_flagged_reels():
    found = {
        "p1": page(("a_ver01", "sn1", "r1", "1850011501"), ("sn1", "r1"), "1850011501"),
        "p2": page(("d_ver01", "sn1", "r1", "1850030101"), ("sn1", "r1"), "1850030101"),
    }

    result = check(found, REEL_MAP)

    assert result["all"]["issues_tested"] == 6 and result["all"]["issues_untested"] == 1
    assert result["flagged"]["hit"]["hits"] == 5 and result["flagged"]["hit"]["n"] == 6
    assert result["reels_with_one_issue_untestable"] == 1
    assert result["pages"] == {
        "flagged_pages": 2,
        "flagged_pages_hit": 1,
        "flagged_candidates": 2,
        "flagged_candidates_hit": 1,
    }


def test_coverage_counts_candidates_with_no_batch_path_on_a_reel_the_map_holds():
    found = {
        "on a mapped reel": page(None, ("sn1", "r1"), "1850040101", candidates=3),
        "on an unmapped reel": page(None, ("sn1", "r9"), "1850040101"),
        "no reel named": page(None, ("sn1", "no_reel"), "1850040101"),
        "a sample only": page(None, ("sn1", "r8"), "1850040101", candidates=0),
        "with a batch path": page(
            ("a_ver01", "sn1", "r1", "1850011501"), ("sn1", "r1"), "1850011501"
        ),
    }

    assert coverage(found, REEL_MAP) == {
        "candidates_with_no_batch_path": 5,
        "covered": 3,
        "covered_share": 0.6,
        "not_covered": 2,
        "not_covered_reels": 2,
        "not_covered_with_no_reel_in_their_member": 1,
    }


def test_the_frame_rule_counts_the_candidates_whose_stored_service_changes_by_batch():
    path = ("a_ver01", "sn1", "r1", "1850011501")
    found = {
        "frame differs": page(path, ("sn1", "r1"), "1850011501", candidates=2)
        | {"changed": True},
        "a sample only": page(path, ("sn1", "r1"), "1850011501", candidates=0)
        | {"changed": True},
        "agrees": page(path, ("sn1", "r1"), "1850011501") | {"changed": False},
        "no batch path": page(None, ("sn1", "r1"), "1850011501"),
    }

    assert frame_rule(found) == {
        "candidates_whose_service_changes": 2,
        "pages_with_candidates": 1,
        "by_batch": {"a_ver01": 2},
    }
