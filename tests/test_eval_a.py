"""Eval A's helpers: OCR quality as the share of words a dictionary knows, and samples that
stand for every article in the archive, not for each year equally."""

from collections import Counter

import pytest
from eval_a import (
    draw,
    flagged,
    ocr_quality,
    summarise_composition,
    summarise_screen,
    uniform,
)

WORDS = frozenset(
    {"the", "ghost", "seen", "every", "night", "family", "report", "walk", "house"}
)


def test_ocr_quality_is_the_share_of_words_the_dictionary_knows():
    text = "The ghost was seen every night; the family re-\nport it walked the houses. Xqzt vvrm."
    # 14 words of three letters or more, and 11 are known once -ed and -s come off
    assert ocr_quality(text, WORDS, least=10) == 11 / 14
    assert ocr_quality("Too short to say.", WORDS) is None


def test_a_recall_sample_weights_each_year_by_its_share_of_the_pool():
    pools = {1800: list(range(100)), 1900: list(range(100)), 1950: list(range(100))}
    sizes = {1800: 1_000, 1900: 99_000, 1950: 0}

    picked = draw(pools, sizes, 50, seed="test")

    years = [year for year, _ in picked]
    assert len(set(picked)) == 50 and 1950 not in years and years.count(1900) > 40
    assert draw(pools, sizes, 50, seed="test") == picked


def test_a_draw_bigger_than_a_years_reservoir_fails_rather_than_shrinking():
    pools = {1800: list(range(5)), 1900: list(range(100))}
    sizes = {1800: 99_000, 1900: 1_000}

    with pytest.raises(AssertionError, match="1800"):
        draw(pools, sizes, 50, seed="test")


def test_a_uniform_pick_gives_every_candidate_the_same_chance():
    counts = {1800: 3, 1801: 0, 1802: 5}
    assert sorted(uniform(counts, 8, seed="x")) == [
        (1800, 0),
        (1800, 1),
        (1800, 2),
        (1802, 0),
        (1802, 1),
        (1802, 2),
        (1802, 3),
        (1802, 4),
    ]


def test_a_story_printed_in_several_papers_counts_once():
    picked = [
        {"category": "ghost_report", "printings": 2},
        {"category": "ghost_report", "printings": 1},
        {"category": "other", "printings": 1},
        {"category": "other", "printings": 4},
    ]
    ghosts = summarise_composition(picked, 400)["categories"]["ghost_report"]
    # each candidate is 1/k of a story when its cluster holds k printings
    assert (ghosts["implied"], ghosts["stories"]) == (200, 150)


def test_the_screen_reads_flag_words_and_near_miss_terms_across_a_line_break():
    assert flagged("A mys-\nterious light, and spirits walking.") == [
        "mysterious",
        "spirits",
    ]
    # the long s, which only the near-miss lexicon reads
    assert flagged("the fpirit of the age") == ["fpirit"]
    assert flagged("The crops were good.") == []


def test_the_screen_bound_counts_the_draw_and_the_300_read_in_full():
    screened = [
        {"article_id": "a", "near_miss_terms": ["spirit"], "first": "no"},
        {"article_id": "b", "near_miss_terms": [], "first": "close"},
    ]
    for item in screened:
        item |= {"rejudged": True, "ghost_report": False, "note": None}
    recalled = [
        {"pool": "random", "article_id": "c", "ghost_report": False},
        {"pool": "near_miss", "article_id": "a", "ghost_report": False},
        {"pool": "near_miss", "article_id": "d", "ghost_report": False},
    ]
    total = {"non_candidates": 1_000_000, "near_miss": 10_000}
    found = {"implied_low": 10, "implied": 20, "implied_high": 40}

    out = summarise_screen(screened, Counter(drawn=99), recalled, [], total, found)

    # 99 drawn and 1 read in full; and a, in both near-miss samples, counts once
    assert (out["random"]["n"], out["near_miss"]["n"]) == (100, 2)
    assert (out["negatives_rejudged"], out["negatives_agreed"]) == (1, 1)
    assert out["recall_at_least"]["point"] == 20 / (20 + out["random"]["implied_high"])
    assert out["recall"] == 1.0  # none missed in the sample
    # no bound while any hit is unread
    screened[1]["ghost_report"] = None
    assert "random" not in summarise_screen(
        screened, Counter(drawn=99), recalled, [], total, found
    )
