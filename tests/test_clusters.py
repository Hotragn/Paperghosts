"""The clustering evaluation's scoring: precision over the labelled pairs the stories keep
together, recall over the pairs labelled one story, and a cluster's least similar pair."""

import numpy as np
from clusters import least_similar, scored


def runs(a, b):
    return np.arange(a, b, dtype=np.uint64)


def test_precision_counts_the_pairs_kept_together_and_recall_those_labelled_one_story():
    index = {"a": 0, "b": 1, "c": 2, "d": 3}
    story = [0, 0, 2, 2]
    labelled = [
        {"pair": "kept and one story", "a": "a", "b": "b", "label": "same"},
        {"pair": "kept but two", "a": "c", "b": "d", "label": "different"},
        {"pair": "split but one", "a": "a", "b": "c", "label": "same"},
        {"pair": "split and two", "a": "b", "b": "d", "label": "different"},
    ]

    found = scored(index, story, labelled)

    assert (found["precision"]["hits"], found["precision"]["n"]) == (1, 2)
    assert (found["recall"]["hits"], found["recall"]["n"]) == (1, 2)
    assert found["false_merges"] == ["kept but two"]
    assert found["false_splits"] == ["split but one"]


def test_a_clusters_least_similar_pair_shares_least_of_the_shorters_shingles():
    found = {"shingles": {0: runs(0, 10), 1: runs(0, 9), 2: runs(5, 15)}}

    # 0 and 1 share all of 1's, 0 and 2 half of theirs, and 1 and 2 four of 1's nine
    assert least_similar(found, [0, 1, 2]) == (1, 2)
