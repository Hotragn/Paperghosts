"""The gold draw (decision 37): a candidate falls in the first stratum that fits, and within a
stratum the draw is systematic in date order, so each article's chance is the stratum's draw
over its size and each stretch of dates gets its share."""

import random
from collections import Counter

from gold_draw import ALLOCATION, stratum, systematic

ROW = {
    "text": "The spirits rapped all evening at the seance in Mrs. Hale's parlour.",
    "date": "1890-01-01",
    "terms": {"seance": ["seance"], "ouija": ["ouija"], "ghost": ["ghost"]},
    "headline": "A GHOST AT THE SEANCE",
}


def test_a_candidate_falls_in_the_first_stratum_that_fits():
    assert stratum(ROW) == "ouija, term in the headline"  # the rarest rule it holds
    assert stratum({**ROW, "terms": {"seance": []}, "headline": ""}) == (
        "seance, none in the headline"
    )
    assert stratum({**ROW, "terms": {"ghost": []}}) == (
        "v1 terms only, term in the headline"
    )
    assert stratum({**ROW, "date": "1849-12-31"}) == "before 1850"
    hoax = {
        **ROW,
        "date": "1849-12-31",
        "text": "The ghost was a hoax, a boy with a sheet.",
    }
    assert stratum(hoax) == "E6: hoaxes and pranksters"
    ship = {**hoax, "text": hoax["text"] + " Then the phantom ship came in."}
    assert stratum(ship) == "E8: phantom ships, trains and lights"
    german = {**ROW, "text": "Der Geist ist nicht da, und die Frau sagt das ein " * 2}
    assert stratum(german) == "E12: not in English"
    assert set(ALLOCATION) >= {stratum(r) for r in (ROW, hoax, ship, german)}


def test_a_systematic_draw_takes_one_from_each_stretch_with_chance_n_over_the_size():
    units = list(range(100))

    picks = systematic(units, 10, random.Random(1))
    drawn = Counter(
        u for seed in range(2000) for u in systematic(units, 10, random.Random(seed))
    )

    assert [p // 10 for p in picks] == list(range(10))
    assert len(drawn) == 100 and all(150 <= c <= 250 for c in drawn.values())
