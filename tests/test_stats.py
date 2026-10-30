"""The evals report their rates with a 95% Wilson score interval."""

import pytest

from paperghosts.stats import wilson


def test_the_wilson_interval_matches_known_values():
    assert wilson(196, 200) == pytest.approx((0.9497, 0.9922), abs=1e-4)
    assert wilson(200, 200) == pytest.approx((0.9812, 1.0), abs=1e-4)
