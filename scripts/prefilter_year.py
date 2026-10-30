"""Runs the prefilter over one streamed faro year file. Writes the year's samples, 2,000
random non-candidates and 2,000 from the near-miss pool, to data/samples/{year}.jsonl.zst.
Prints the candidate count, the candidates per term with how many that term alone keeps,
the near-miss count, and 15 candidates sampled with the year as the seed.

Run with `uv run python scripts/prefilter_year.py 1850`.
"""

import random
import sys
import time
from pathlib import Path

from paperghosts.ingest.lexicon import VERSION
from paperghosts.ingest.prefilter import scan, write_jsonl_zst
from paperghosts.ingest.stream import FARO, pages

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def first_line(text):
    return next(
        (line.strip() for line in (text or "").splitlines() if line.strip()), ""
    )


def main(year):
    start = time.perf_counter()
    result = scan(pages(FARO.format(year=year)), year)
    seconds = time.perf_counter() - start
    write_jsonl_zst(
        SAMPLES / f"{year}.jsonl.zst",
        [
            {"sample": name, **item}
            for name, items in result["samples"].items()
            for item in items
        ],
    )

    articles, candidates = result["articles"], result["candidates"]
    print(f"lexicon {VERSION}, faro_{year}: {articles:,} articles in {seconds:.0f} s")
    print(
        f"candidates: {len(candidates):,} ({len(candidates) / articles * 1e6:,.0f} per million)"
    )
    print(f"near-miss articles, with no ghost term: {result['near_miss']:,}")
    sizes = ", ".join(
        f"{len(items):,} {name}" for name, items in result["samples"].items()
    )
    print(f"samples written to data/samples/{year}.jsonl.zst: {sizes}")
    print(
        "candidates per term, how many that term alone keeps, and the commonest spellings:"
    )
    for term, count in result["per_term"].most_common():
        forms = [(f, n) for (t, f), n in result["spellings"].most_common() if t == term]
        spelled = ", ".join(f"{f} {n:,}" for f, n in forms[:4])
        print(f"  {term:<12}{count:>6,}  only {result['only'][term]:>5,}   {spelled}")
    print(f"15 candidates, seed {year}:")
    for c in random.Random(year).sample(candidates, min(15, len(candidates))):
        forms = ", ".join(form for forms in c["terms"].values() for form in forms)
        print(f"- {c['date']}  {(c['paper'] or '')[:45]}  [{forms}]")
        print(
            f"  headline:   {' '.join((c['headline'] or '').split())[:110] or '(none)'}"
        )
        print(f"  first line: {first_line(c['text'])[:110]}")


if __name__ == "__main__":
    main(int(sys.argv[1]))
