"""A demo report's field goes to Atlas with its value only when its quote verified."""

from load_demo_atlas import stated


def test_a_verified_field_keeps_its_value_and_quote():
    field = {
        "value": "the old farmhouse",
        "quote": "the old farmhouse",
        "verified": True,
    }
    assert stated(field) == {**field, "score": 1.0}


def test_an_unverified_or_missing_field_is_not_stated():
    assert stated({"value": "x", "quote": "y", "verified": False}) == {
        "verified": False,
        "score": 0.0,
    }
    assert stated(None) == {"verified": False, "score": 0.0}
