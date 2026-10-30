"""Runs the lexicon over one streamed faro year file and prints what it keeps: the candidate
count, the candidates per term with their scanned spellings, the near-miss count, and 15
candidates sampled with the year as the seed. It writes nothing; the ingest workflow will.

Run with `uv run python scripts/prefilter_year.py 1850`.
"""

import random
import sys
import time
from collections import Counter

from paperghosts.ingest.lexicon import VERSION, ghost_terms, near_miss_terms
from paperghosts.ingest.stream import FARO, pages


def first_line(text):
    return next(
        (line.strip() for line in (text or "").splitlines() if line.strip()), ""
    )


def main(year):
    start = time.perf_counter()
    articles = near_miss = 0
    per_term, spellings = Counter(), Counter()
    candidates = []
    for _, page in pages(FARO.format(year=year)):
        for article in page.get("full articles") or []:
            articles += 1
            headline = article.get("headline") or ""
            text = f"{headline}\n{article.get('article') or ''}"
            terms = ghost_terms(text)
            if terms:
                per_term.update(terms.keys())
                spellings.update(
                    (term, form) for term, forms in terms.items() for form in forms
                )
                candidates.append(
                    {
                        "paper": page["lccn"]["title"],
                        "date": page["edition"]["date"],
                        "forms": [form for forms in terms.values() for form in forms],
                        "headline": " ".join(headline.split()),
                        "first_line": first_line(article.get("article")),
                    }
                )
            elif near_miss_terms(text):
                near_miss += 1

    print(
        f"lexicon {VERSION}, faro_{year}: {articles:,} articles in {time.perf_counter() - start:.0f} s"
    )
    print(
        f"candidates: {len(candidates):,} ({len(candidates) / articles * 1e6:,.0f} per million)"
    )
    print(f"near-miss articles, with no ghost term: {near_miss:,}")
    print("candidates per term, with their most common spellings:")
    for term, count in per_term.most_common():
        top = [(f, n) for (t, f), n in spellings.most_common() if t == term][:4]
        print(f"  {term:<12}{count:>6,}   " + ", ".join(f"{f} {n:,}" for f, n in top))
    print(f"15 candidates, seed {year}:")
    for c in random.Random(year).sample(candidates, min(15, len(candidates))):
        print(f"- {c['date']}  {c['paper'][:45]}  [{', '.join(c['forms'])}]")
        print(f"  headline:   {c['headline'][:110] or '(none)'}")
        print(f"  first line: {c['first_line'][:110]}")


if __name__ == "__main__":
    main(int(sys.argv[1]))
