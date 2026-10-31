"""The training draw: gold's allocation scaled, one printing per story, and the split's rules
and the stricter reprint rule checked on it."""

from training_draw import allocation, drawn, problems


def test_the_allocation_is_golds_scaled_to_the_size():
    sizes = allocation(600)
    assert sum(sizes.values()) == 600
    assert sizes["v1 terms only, term in the headline"] == 160  # 80 of gold's 300
    assert all(v > 0 for v in sizes.values())


def test_a_story_is_drawn_once_however_many_printings_or_strata_hold_it():
    group = {"a1": "g1", "a2": "g1", "b1": "g2", "c1": "g3", "c2": "g4"}
    units = {
        "s1": [("1880", "a1"), ("1881", "a2"), ("1882", "b1")],
        "s2": [("1883", "a2"), ("1884", "c1"), ("1885", "c2")],
    }
    picked = drawn(units, {"s1": 2, "s2": 3}, group, "seed")
    stories = [group[aid] for aid, _ in picked]
    assert len(stories) == len(set(stories)) == 4
    assert ("a1", "s1") in picked and "a2" not in [
        a for a, _ in picked
    ]  # the earliest printing
    assert picked == drawn(units, {"s1": 2, "s2": 3}, group, "seed")


def test_the_split_rules_find_a_held_article_and_a_story_drawn_twice():
    split = {"out_of_pool": ["held"]}
    found = problems(["held", "a1", "a2"], split, {"a1": "g", "a2": "g"})
    assert found == {"outside_the_pool": ["held"], "stories_drawn_twice": ["g"]}
