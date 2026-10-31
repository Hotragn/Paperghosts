"""The demo export places each quote in the OCR text, across any spacing, or says it can't."""

from export_demo import span


def test_a_quote_is_found_across_line_breaks_and_case():
    text = "the house of MIR.\nParsons, the pous parish clerk"
    assert span("house of mir. Parsons", text) == [4, 25]


def test_a_quote_not_in_the_text_has_no_place():
    assert span("a headless horseman", "knockings upon the walls") is None
    assert span("", "anything") is None
