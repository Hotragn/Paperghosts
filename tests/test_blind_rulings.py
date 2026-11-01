"""Fresh judges rule blind on each dispute: two labels as A and B, no names or notes, and their
rulings are compared with the first labeller's."""

from blind_rulings import cases, compared, masked, problems

TEXT = "A HAUNTED FARMHOUSE The family of Mr. John Hale heard knockings upon the walls of the old farmhouse."


def label(kind, labeller, **fields):
    return {
        "article_id": "a",
        "kind": kind,
        "kind_quote": "knockings",
        "labeller": labeller,
        "note": "mine",
        **fields,
    }


def test_a_judge_sees_two_unnamed_labels_in_a_seeded_order():
    shown = masked(label("report", "Claude", rules=[1]))
    assert shown == {"kind": "report", "kind_quote": "knockings"}
    disputed = [
        {
            "article_id": f"a{i}",
            "kinds": ["other", "idiom"],
            "fields": [],
            "first": label("other", "Claude"),
            "second": label("idiom", "second pass"),
        }
        for i in range(10)
    ]
    made, key = cases(disputed)
    assert (made, key) == cases(list(reversed(disputed)))
    assert {k["A"] for k in key.values()} == {"first", "second"}
    for c in made:
        first_is_a = key[c["case"]]["A"] == "first"
        assert c["A"]["kind"] == ("other" if first_is_a else "idiom")
        assert (
            "labeller" not in c["A"]
            and "note" not in c["B"]
            and c["disputed"] == ["kind"]
        )


def test_rulings_are_compared_by_kind_and_field_and_by_which_side_won():
    first = label(
        "report",
        "Claude",
        seen={"value": "knockings", "quote": "knockings upon the walls"},
    )
    second = label(
        "report",
        "second pass",
        seen={"value": "the farmhouse", "quote": "the old farmhouse"},
    )
    other = {
        "article_id": "b",
        "kinds": ["other", "idiom"],
        "fields": [],
        "first": label("other", "Claude"),
        "second": label("idiom", "x"),
        "ruling": label("other", "ruling"),
    }
    disputed = {
        "a": {
            "article_id": "a",
            "kinds": ["report", "report"],
            "fields": ["seen"],
            "first": first,
            "second": second,
            "ruling": first,
        },
        "b": other,
    }
    key = {
        "c01": {"article_id": "a", "A": "second"},
        "c02": {"article_id": "b", "A": "first"},
    }
    rulings = [
        {
            "case": "c01",
            "fields": {"seen": {"value": "the farmhouse", "quote": "old farmhouse"}},
        },
        {"case": "c02", "kind": "other"},
    ]
    found = compared(rulings, key, disputed, {"a": TEXT, "b": TEXT})
    assert (found["seen"]["agree"], found["seen"]["won"]["second"]) == (0, 1)
    assert (found["kind"]["agree"], found["kind"]["won"]["first"]) == (1, 1)
    assert (
        problems(
            rulings,
            {
                "c01": {"headline": "", "text": TEXT},
                "c02": {"headline": "", "text": TEXT},
            },
        )
        == []
    )
    assert problems(
        [rulings[0]],
        {
            "c01": {"headline": "", "text": "nothing"},
            "c02": {"headline": "", "text": ""},
        },
    )


def test_a_blind_ruling_that_differs_replaces_the_kind_or_the_field():
    from blind_rulings import settled

    first = label(
        "report",
        "Claude",
        seen={"value": "knockings", "quote": "knockings upon the walls"},
    )
    d = {"kinds": ["report", "report"], "fields": ["seen"], "ruling": first}
    blind = {
        "case": "c01",
        "fields": {"seen": {"value": "the farmhouse", "quote": "the old farmhouse"}},
    }
    assert settled(blind, d, TEXT)["seen"]["value"] == "the farmhouse"
    assert settled({"case": "c01", "fields": {"seen": first["seen"]}}, d, TEXT) is None

    kinds = {"kinds": ["report", "idiom"], "fields": [], "ruling": first}
    idiom = settled(
        {"case": "c02", "kind": "idiom", "kind_quote": "knockings"}, kinds, TEXT
    )
    assert idiom["kind"] == "idiom" and idiom["seen"] is None and idiom["people"] == []
