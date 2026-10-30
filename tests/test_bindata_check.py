"""The BinData check's ground truth: numpy's nearest neighbours by cosine, scored as Atlas
scores them."""

import numpy as np
from bindata_check import nearest


def test_nearest_ranks_by_cosine_and_breaks_ties_by_id():
    docs = np.array([[1, 0], [0, 1], [2, 0], [1, 1], [-1, 0]], dtype=np.float32)

    ids, scores = nearest(docs, np.array([1, 0], dtype=np.float32), k=3)

    # 0 and 2 point the same way as the query, so the lower id comes first
    assert ids == [0, 2, 3]
    assert np.allclose(scores, [1.0, 1.0, (1 + 2**-0.5) / 2])
