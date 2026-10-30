"""Eval A's bar charts take a text label at the end of a row, and a bar of zero still has
something to hover over."""

from charts import bars, nice, pct


def test_a_bar_row_can_end_in_a_label_and_a_zero_still_has_a_tooltip(tmp_path):
    path = bars(
        tmp_path / "recall.svg",
        "Ghost reports the lexicon missed",
        "subtitle",
        [("Near-miss pool", 0.0, "0 of 300"), ("Candidates", 3.5, "7 of 200")],
        lambda v: f"{v:.1f}%",
        intervals=[(0.0, 1.26), (1.7, 7.0)],
    )
    svg = path.read_text()
    assert "0 of 300" in svg and "7 of 200" in svg
    assert "<title>Near-miss pool: 0 of 300</title>" in svg


def test_an_axis_under_one_gets_a_step_under_one():
    # the recall chart's top is a 1.26% interval; it once got a 0–10% axis
    assert nice(1.26) == (1.5, 0.5)
    assert nice(46.4) == (60, 20)


def test_a_small_share_keeps_two_figures():
    assert [pct(v) for v in (0.035, 0.0101, 0.0015, 0.00004, 0)] == [
        "3.5%",
        "1.0%",
        "0.15%",
        "0.0040%",
        "0.0%",
    ]
