"""Small statistics the evals share."""

import math


def wilson(hits, n, z=1.96):
    """The Wilson score interval for hits out of n, 95% by default."""
    p, z2 = hits / n, z * z
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return max(0.0, centre - half), min(1.0, centre + half)
