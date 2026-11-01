"""The format check reads a bare schema value as that value and empties a value outside the schema."""

from format_check import normalised


def test_a_bare_schema_value_is_read_without_a_quote():
    assert normalised("outcome", "hoax") == {"value": "hoax", "quote": ""}


def test_a_value_outside_the_schema_is_left_empty():
    assert normalised("outcome", "spooky") is None
    assert (
        normalised("place_state", {"value": "Philadelphia", "quote": "Philadelphia"})
        is None
    )


def test_a_well_formed_value_keeps_its_quote():
    given = {"value": "Maryland", "quote": "Baltimore"}
    assert normalised("place_state", given) == given
