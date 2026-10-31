"""Every number is read from its source and names it."""

from article_numbers import entries


def test_every_number_has_a_value_and_a_source():
    found = entries()
    assert found
    for e in found:
        assert e["name"] and e["source"] and e["value"] is not None, e
    assert len({e["name"] for e in found}) == len(found)
