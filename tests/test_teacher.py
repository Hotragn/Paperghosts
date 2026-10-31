"""The teacher's prompt, the parse of its answer, and the quote verifier that drops any value
whose quote isn't in the article."""

from teacher import parsed, prompt_sha256, rendered, score, verified

TEXT = "A HAUNTED FARMHOUSE MILFORD, Conn., June 3.-The family of Mr. John Hale have been disturbed every night by knockings upon the walls of the old farmhouse."


def test_the_prompt_is_chatml_without_thinking_and_hashed():
    text = rendered("the system", "the article")
    assert text.startswith(
        "<|im_start|>system\nthe system<|im_end|>\n<|im_start|>user\nthe article"
    )
    assert text.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    assert prompt_sha256("a") != prompt_sha256("b") and len(prompt_sha256("a")) == 64


def test_an_answer_is_parsed_from_its_json_even_with_text_around_it():
    answer = 'Here it is: {"kind": "report", "kind_quote": "knockings", "seen": {"value": "knockings", "quote": "knockings upon the walls"}, "people": []} done'
    found = parsed(answer)
    assert (
        found["kind"] == "report"
        and found["seen"]["quote"] == "knockings upon the walls"
    )
    assert parsed("no json here") is None
    assert parsed('{"kind": "spooky"}') is None  # not one of POLICY.md's kinds


def test_a_quote_scores_one_when_it_is_in_the_text_and_low_when_it_is_not():
    assert score("knockings upon the walls", TEXT) == 1.0
    assert (
        score("Knockings  upon the WALLS.", TEXT) == 1.0
    )  # case, spacing and punctuation
    assert 0.8 < score("knockings upon tho walls", TEXT) < 1.0  # an OCR letter mended
    assert score("a pale woman in white on the stairs", TEXT) < 0.6


def test_a_value_whose_quote_fails_is_dropped_never_kept():
    label = {
        "kind": "report",
        "kind_quote": "knockings",
        "seen": {"value": "knockings", "quote": "knockings upon the walls"},
        "place": {"value": "Boston", "quote": "in the city of Boston"},
        "outcome": {"value": "spooky", "quote": "knockings"},
        "people": [
            {"value": "the Hale family", "quote": "The family of Mr. John Hale"},
            {"value": "a ghost", "quote": "a pale ghost"},
        ],
    }
    kept, dropped = verified(label, TEXT, 0.9)
    assert kept["seen"]["quote"] == "knockings upon the walls" and kept["place"] is None
    assert kept["outcome"] is None  # not one of the schema's outcomes
    assert [p["value"] for p in kept["people"]] == ["the Hale family"]
    assert sorted(dropped) == ["outcome", "people", "place"]


def test_a_malformed_field_is_dropped_at_the_parse():
    found = parsed(
        '{"kind": "report", "kind_quote": "x", "seen": "knockings", "place": {"value": "the farm", "quote": "the old farmhouse"}, "people": ["the family", {"value": "Mr. Hale", "quote": "Mr. John Hale"}]}'
    )
    assert found["seen"] is None and found["place"]["value"] == "the farm"
    assert found["people"] == [{"value": "Mr. Hale", "quote": "Mr. John Hale"}]


def test_the_answer_is_what_follows_the_reasoning_and_kind_goes_by_majority():
    from teacher import final, voted

    assert (
        final('<think>maybe idiom {x}</think>\n\n{"kind": "report"}<|im_end|>')
        == '\n\n{"kind": "report"}'
    )
    assert (
        final(
            '<|channel|>analysis<|message|>{"no"}<|end|><|start|>assistant<|channel|>final<|message|>{"kind": "other"}<|return|>'
        )
        == '{"kind": "other"}'
    )
    a = '{"kind": "report", "kind_quote": "first"}'
    b = '{"kind": "other", "kind_quote": "second"}'
    c = '{"kind": "report", "kind_quote": "third"}'
    assert (
        voted([b, a, c])["kind_quote"] == "first"
    )  # the first that agrees with the majority
    assert (
        voted([b, a, "junk"])["kind_quote"] == "second"
    )  # no majority: the first parsed
    assert voted(["junk"]) is None
