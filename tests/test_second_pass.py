"""The blind second pass: every gold article and a seeded fifth of dev, labelled again from the
text, its crops and POLICY.md alone, and how far it agrees with the first pass, with 95%
intervals, before any ruling."""

import pytest
from second_pass import (
    agreed,
    disputes,
    interval,
    kappa,
    packets,
    passed,
    same,
    sampled,
)

TEXT = (
    "MILFORD, Conn., June 3.-The family of Mr. John Hale have been disturbed every night "
    "by knockings upon the walls of the old farmhouse, which no search has been able to explain."
)
ROW = {"headline": "A HAUNTED FARMHOUSE", "text": TEXT, "paper": "The Courant"}


def quoted(quote, value=None):
    return {"value": value or quote, "quote": quote}


def report(**fields):
    return {
        "kind": "report",
        "place": quoted("the old farmhouse"),
        "place_state": quoted("Conn.", "Connecticut"),
        "seen": quoted("knockings upon the walls"),
        "outcome": quoted("which no search has been able to explain", "unexplained"),
        "specific_place": None,
        "place_type": None,
        "precision": None,
        "people": [quoted("The family of Mr. John Hale")],
        **fields,
    }


def test_the_dev_share_is_a_seeded_fifth_and_the_pass_is_all_of_gold_with_it():
    dev = [f"d{i:03}" for i in range(150)]
    picked = sampled(dev)
    assert len(picked) == 30 and picked == sorted(picked) and set(picked) <= set(dev)
    assert picked == sampled(list(reversed(dev)))  # the seed decides, not the order
    assert picked != sorted(dev)[:30]

    rows = {f"g{i}": {"split": "gold"} for i in range(4)} | {
        aid: {"split": "dev"} for aid in dev
    }
    order = passed(rows)
    assert sorted(order) == sorted([f"g{i}" for i in range(4)] + picked)
    assert order == passed(dict(reversed(list(rows.items()))))
    assert order != [f"g{i}" for i in range(4)] + picked  # shuffled, so no split shows


def test_a_packet_shows_the_text_and_its_crops_and_nothing_of_the_split():
    rows = {
        f"a{i}": dict(ROW, split="gold", stratum="a stratum", weight=7.5)
        for i in range(5)
    }
    cropped = {"a0": {"crops": ["/crops/0123.jpg"]}, "a1": {"none": "no boxes"}}

    made = packets(rows, list(rows), 2, cropped)
    assert [len(texts) for _, texts in made] == [3, 2]
    shown, texts = made[0]
    assert "knockings upon the walls" in shown and "/crops/0123.jpg" in shown
    assert "no boxes" in shown
    assert not any(word in shown for word in ("stratum", "7.5", "gold"))
    assert texts["a0"] == {"headline": ROW["headline"], "text": TEXT}


def test_kappa_is_cohens_and_is_undefined_when_chance_explains_everything():
    a = ["yes"] * 25 + ["no"] * 25
    b = ["yes"] * 20 + ["no"] * 5 + ["yes"] * 10 + ["no"] * 15
    assert kappa(a, b) == pytest.approx(0.4)
    low, high = interval(a, b)
    assert 0.05 < low < 0.4 < high < 0.75
    assert kappa(a, a) == 1.0
    assert kappa(["idiom"] * 4, ["idiom"] * 4) is None


def test_a_field_agrees_on_a_value_or_on_quotes_that_overlap():
    text = " ".join(f"{ROW['headline']}\n{TEXT}".split())
    first = report()

    assert same("place", first, report(place=quoted("walls of the old farm")), text)
    assert not same("place", first, report(place=quoted("MILFORD")), text)
    assert not same("place", first, report(place=None), text)
    assert same("specific_place", first, report(), text)  # both empty
    assert same(
        "place", first, report(place=quoted("Milford", "the Old Farmhouse")), text
    )
    assert not same("outcome", first, report(outcome=quoted("Conn.", "unknown")), text)
    assert same(
        "place_state",
        first,
        report(place_state=quoted("MILFORD, Conn.", "Connecticut")),
        text,
    )

    both = [quoted("The family of Mr. John Hale"), quoted("Mr. John Hale")]
    assert same(
        "people", report(people=both), report(people=[quoted("family of Mr.")]), text
    )
    assert not same("people", first, report(people=both + [quoted("MILFORD")]), text)
    assert not same("people", first, report(people=[]), text)


def test_agreement_counts_kind_report_and_fields_with_their_intervals():
    texts = {aid: " ".join(f"{ROW['headline']}\n{TEXT}".split()) for aid in "abc"}
    pairs = [
        (
            {"article_id": "a", **report()},
            {"article_id": "a", **report(place=quoted("MILFORD"))},
        ),
        ({"article_id": "b", **report()}, {"article_id": "b", "kind": "fiction"}),
        ({"article_id": "c", "kind": "idiom"}, {"article_id": "c", "kind": "idiom"}),
    ]

    found = agreed(pairs, texts)
    assert found["n"] == 3
    assert (found["kind"]["agree"], found["report"]["agree"]) == (2, 2)
    assert found["kind"]["interval"] == pytest.approx((0.208, 0.939), abs=1e-3)
    assert found["kind"]["kappa"] == pytest.approx(0.5)
    assert len(found["kind"]["kappa_interval"]) == 2
    assert found["fields"]["outcome"] == {
        "agree": 1,
        "n": 1,
        "rate": 1.0,
        "interval": pytest.approx((0.2065, 1.0), abs=1e-4),
    }
    assert found["fields"]["place"]["agree"] == 0

    assert disputes(pairs, texts) == [
        {"article_id": "a", "kinds": ["report", "report"], "fields": ["place"]},
        {"article_id": "b", "kinds": ["report", "fiction"], "fields": []},
    ]
