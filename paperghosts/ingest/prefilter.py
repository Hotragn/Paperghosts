"""The prefilter's pass over one year: the candidates, their term counts, and fixed-size
samples of the non-candidates, which measure its recall (ARCHITECTURE section 3.1)."""

import random
from collections import Counter

import orjson
import zstandard

from paperghosts.ingest.lexicon import ghost_terms, near_miss_terms

SAMPLE_SIZE = 2000


class Reservoir:
    """A uniform sample of fixed size from a stream of unknown length (Algorithm R)."""

    def __init__(self, size, rng):
        self.size, self.rng, self.seen, self.items = size, rng, 0, []

    def offer(self, item):
        if len(self.items) < self.size:
            self.items.append(item)
        else:
            slot = self.rng.randrange(self.seen + 1)
            if slot < self.size:
                self.items[slot] = item
        self.seen += 1


def record(member, page, article, **found):
    lccn = page.get("lccn") or {}
    return {
        "member": member,
        "article_id": article.get("id"),
        "lccn": lccn.get("lccn"),
        "paper": lccn.get("title"),
        "state": lccn.get("state"),
        "date": (page.get("edition") or {}).get("date"),
        "scan": page.get("scan"),
        "headline": article.get("headline"),
        "text": article.get("article"),
        "bbox_list": article.get("bbox_list"),
        **found,
    }


def scan(pages, year, sample_size=SAMPLE_SIZE):
    """Sorts every article of one year into candidates, the near-miss pool and the rest,
    keeping seeded reservoir samples of the near-miss pool and of all non-candidates."""
    random_sample = Reservoir(sample_size, random.Random(f"{year} random"))
    near_miss_sample = Reservoir(sample_size, random.Random(f"{year} near-miss"))
    result = {"articles": 0, "near_miss": 0, "candidates": []}
    per_term, only, spellings = Counter(), Counter(), Counter()
    for member, page in pages:
        for article in page.get("full articles") or []:
            result["articles"] += 1
            text = f"{article.get('headline') or ''}\n{article.get('article') or ''}"
            terms = ghost_terms(text)
            if terms:
                result["candidates"].append(record(member, page, article, terms=terms))
                per_term.update(terms.keys())
                only.update(terms.keys() if len(terms) == 1 else ())
                spellings.update(
                    (t, form) for t, forms in terms.items() for form in forms
                )
                continue
            near = near_miss_terms(text)
            item = record(member, page, article, near_miss_terms=near)
            random_sample.offer(item)
            if near:
                result["near_miss"] += 1
                near_miss_sample.offer(item)
    result.update(per_term=per_term, only=only, spellings=spellings)
    result["samples"] = {
        "random": random_sample.items,
        "near_miss": near_miss_sample.items,
    }
    return result


def write_jsonl_zst(path, records):
    """Writes the records to a partial file first, so a crash never leaves a short one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    with zstandard.open(partial, "wb") as out:
        for item in records:
            out.write(orjson.dumps(item) + b"\n")
    partial.replace(path)
