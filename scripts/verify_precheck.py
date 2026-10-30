"""Proves the lexicon's pre-check changes nothing: over one streamed year, every article's
ghost and near-miss terms come out the same with it and without it. Prints the count of
articles that differ and the lexicon's CPU seconds each way.

Run with `uv run python scripts/verify_precheck.py 1850`.
"""

import sys
import time

from paperghosts.ingest.lexicon import ghost_terms, near_miss_terms
from paperghosts.ingest.stream import FARO, pages


def main(year):
    articles = differ = 0
    cpu = {True: 0.0, False: 0.0}
    for _, page in pages(FARO.format(year=year)):
        for article in page.get("full articles") or []:
            articles += 1
            text = f"{article.get('headline') or ''}\n{article.get('article') or ''}"
            found = {}
            for precheck in (True, False):
                start = time.process_time()
                found[precheck] = (
                    ghost_terms(text, precheck),
                    near_miss_terms(text, precheck),
                )
                cpu[precheck] += time.process_time() - start
            differ += found[True] != found[False]
    print(f"faro_{year}: {articles:,} articles, {differ} with different terms")
    print(
        f"lexicon CPU: {cpu[True]:.1f} s with the pre-check, {cpu[False]:.1f} s without"
    )


if __name__ == "__main__":
    main(int(sys.argv[1]))
