"""Printings of one story share runs of words, give or take OCR errors and an extra line at
the start. An unrelated article doesn't join them, nor does stock phrasing that too many
articles share, nor one quoted run on its own. And a printing joins a story only by matching
its first printing directly, never through a chain of links (decision 36)."""

import numpy as np

from paperghosts.cluster.reprints import (
    clusters,
    groups,
    keys,
    overlap,
    shingles,
    stories,
)

STORY = (
    "A strange story comes from the village of Milford, where the family of Mr. John Hale "
    "have been disturbed every night for a fortnight by knockings upon the walls of the old "
    "farmhouse which no search has been able to explain. The neighbors who have sat up with "
    "the family declare that they heard the sounds plainly and saw nothing at all, and the "
    "minister who visited the house on Sunday says he cannot account for the noises, though "
    "he does not believe that spirits have anything to do with them."
)
# the same story in another paper: a credit line first, and a few words misread
REPRINT = "From the Hartford Courant.\n" + STORY.replace(
    "farmhouse", "farmhonse"
).replace("fortnight", "fortuight")
OTHER = (
    "The county commissioners met on Tuesday and voted to repair the bridge over Mill creek "
    "before the spring freshets, the contract going to the lowest bidder. The treasurer "
    "reported that the taxes for the year have been nearly all collected, and that the county "
    "will close the year with a balance in the treasury for the first time since the war."
)


def test_printings_of_one_story_cluster_and_others_stay_apart():
    assert keys(STORY) and keys(STORY) & keys(REPRINT)
    assert clusters([keys(STORY), keys(OTHER), keys(REPRINT)]) == [[0, 2]]


def test_a_key_too_many_articles_share_is_stock_phrasing():
    assert clusters([{7}, {7}, {7}], boilerplate=2) == []
    assert clusters([{7}, {7}, {8}], boilerplate=2) == [[0, 1]]


def test_one_shared_run_is_a_quotation_and_joins_nothing():
    # in the hand check, a single shared run was a quoted verse or a stock phrase
    assert clusters([{1, 2}, {1, 3}], least=2) == []
    assert clusters([{1, 2, 5}, {1, 2, 6}, {7}], least=2) == [[0, 1]]
    assert clusters([keys(STORY), keys(OTHER), keys(REPRINT)], least=2) == [[0, 2]]


def runs(*spans):
    """Shingles standing for texts: each span of numbers is a stretch of runs."""
    return np.array(sorted({i for a, b in spans for i in range(a, b)}), dtype=np.uint64)


def test_a_reprint_through_ocr_errors_holds_most_of_the_storys_runs_and_another_none():
    shared, of_shorter, _ = overlap(shingles(STORY), shingles(REPRINT))

    assert shared and of_shorter >= 0.5
    assert overlap(shingles(STORY), shingles(OTHER))[0] == 0


def test_a_cut_reprint_is_held_whole_in_its_original_which_it_holds_only_half_of():
    assert overlap(runs((0, 40)), runs((0, 20))) == (20, 1.0, 0.5)
    assert overlap(runs((0, 10)), np.array([], dtype=np.uint64)) == (0, 0.0, 0.0)


def test_a_printing_linked_only_through_another_doesnt_join_the_story():
    # 0 is a story, 1 a column printing it and another, 2 the other: 1 links them both
    keys = [{1, 2}, {1, 2, 3, 4}, {3, 4}]
    texts = [runs((0, 10)), runs((0, 20)), runs((10, 20))]

    story, match = stories(keys, texts, order=[0, 1, 2], threshold=0.5)

    assert story == [0, 0, 2] and match == [1.0, 1.0, 1.0]


def test_a_printing_linked_to_two_stories_joins_the_one_it_matches_best():
    keys = [{1, 2}, {3, 4}, {1, 2, 3, 4}]
    texts = [runs((0, 10)), runs((20, 30)), runs((0, 4), (20, 29))]

    story, match = stories(keys, texts, order=[0, 1, 2], threshold=0.3)

    assert story == [0, 1, 1] and match[2] == 9 / 10


def test_the_first_printing_names_the_story_and_a_weak_match_starts_its_own():
    keys = [{1, 2}, {1, 2}, {1, 2}]
    texts = [runs((0, 10)), runs((0, 10)), runs((0, 3), (50, 60))]

    story, _ = stories(keys, texts, order=[1, 0, 2], threshold=0.5)

    assert story == [1, 1, 2]


def test_a_run_pair_too_many_printings_share_links_nothing():
    keys = [{1, 2}, {1, 2}, {1, 2}]
    texts = [runs((0, 10))] * 3

    assert stories(keys, texts, order=[0, 1, 2], threshold=0.5, boilerplate=2)[0] == [
        0,
        1,
        2,
    ]


def test_runs_can_come_from_the_body_as_well_as_the_opening():
    # the body probe: a reprint whose opening was rewritten still shares its body's runs
    body = " ".join(
        f"word{chr(97 + i % 26)}{chr(97 + i // 26 % 26)}" for i in range(400)
    )
    rewritten = "An entirely new opening paragraph about something else. " * 30 + body

    assert keys(body, start=120) and keys(body, start=120) == keys(body, start=120)
    assert keys(body) != keys(body, start=120)
    assert not keys(rewritten) & keys(body)


def test_the_leakage_check_compares_every_run_of_the_whole_text():
    # check_leakage (RDR-4) reads all of each text, past the stories' 600 words, unsampled
    long = " ".join(
        f"word{chr(97 + i % 26)}{chr(97 + i // 26 % 26)}{chr(97 + i // 676)}"
        for i in range(700)
    )
    every = shingles(long, window=None, sample=1)

    assert len(every) == 700 - 4
    assert len(shingles(long)) < len(every) / 2
    assert set(shingles(long)) <= set(every)


def test_the_split_groups_printings_linked_by_the_opening_or_the_body_through_any_chain():
    # decision 37: eval A's links and the body's, chained, so no reprint crosses the split
    opening = [{1, 2}, {1, 2}, {9}, {20}]
    body = [{9}, {5, 6}, {5, 6}, {21}]

    assert groups(opening, body) == [[0, 1, 2]]
    # a story printed under a new lead: its opening is the other printing's body
    assert groups([{1, 2}, {7, 8}], [{30}, {1, 2}]) == [[0, 1]]
