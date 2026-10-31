"""Reprint clusters: a syndicated story was printed in many papers in the same words, give or
take OCR errors, so articles that share runs of words are taken for printings of one story.
Eval A's clusters (`clusters`) join every pair of printings that share two runs, so a chain of
such links can join stories that share nothing. The stories (`stories`, decision 36) keep
those links, but a printing joins a story only by matching its first printing directly."""

import re
import zlib

import numpy as np

WORD = re.compile(r"[a-z]{3,}")
RUN, OPENING, ONE_IN = 7, 120, 8  # words per run, words read, one run kept in ONE_IN
BOILERPLATE = 1000  # a run more articles than this share is stock phrasing, not a story
DOC_BITS = 21  # room for 2 million documents beside each key
SKETCH = 6  # the smallest keys a document is paired on
MASK64 = (1 << 64) - 1
SHINGLE, WINDOW, SAMPLE = (
    5,
    600,
    4,
)  # words per shingle, words read, one shingle kept in 4


def keys(text, start=0):
    """64-bit hashes of a sample of the seven-word runs in the article's opening, its first 120
    words of 3+ letters, or in the 120 from word `start`. A run is kept by its own hash, so the
    sample doesn't shift when one printing has an extra line."""
    words = WORD.findall(
        (text or "")[: 50 * (start + OPENING)].replace("-\n", "").lower()
    )
    words = words[start : start + OPENING]
    found = set()
    for i in range(len(words) - RUN + 1):
        run = " ".join(words[i : i + RUN]).encode()
        low = zlib.crc32(run)
        # a second, differently seeded CRC keeps chance collisions out of a million articles
        if low % ONE_IN == 0:
            found.add(zlib.crc32(run, 0x5BD1E995) << 32 | low)
    return found


def pairs(held, sketch=SKETCH):
    """Keys for each pair among the document's `sketch` smallest keys. Printings of one text
    share their smallest keys, as a MinHash does, so two printings sharing two runs share a
    pair, and a document sharing only one run (a quoted verse, a stock phrase) shares none."""
    low = sorted(held)[:sketch]
    return {
        (a * 0x9E3779B97F4A7C15 ^ b) & MASK64
        for i, a in enumerate(low)
        for b in low[i + 1 :]
    }


def clusters(doc_keys, boilerplate=BOILERPLATE, least=1):
    """The groups of two or more documents linked by shared keys, as sorted lists of their
    indexes; with least=2, documents must share two keys to be linked. Keys are sorted with
    their documents packed beside them, which takes far less memory than a dictionary of
    lists for a million articles."""
    assert len(doc_keys) < 1 << DOC_BITS
    if least == 2:
        doc_keys = [pairs(held) for held in doc_keys]
    parent = list(range(len(doc_keys)))

    def root(doc):
        while parent[doc] != doc:
            parent[doc] = parent[parent[doc]]
            doc = parent[doc]
        return doc

    mask = (1 << DOC_BITS) - 1
    entries = sorted(
        key << DOC_BITS | doc for doc, held in enumerate(doc_keys) for key in held
    )
    start = 0
    for end in range(1, len(entries) + 1):
        if (
            end < len(entries)
            and entries[end] >> DOC_BITS == entries[start] >> DOC_BITS
        ):
            continue
        if 2 <= end - start <= boilerplate:
            first = root(entries[start] & mask)
            for entry in entries[start + 1 : end]:
                other = root(entry & mask)
                if other != first:
                    parent[other] = first
        start = end
    groups = {}
    for doc in range(len(doc_keys)):
        groups.setdefault(root(doc), []).append(doc)
    return [group for group in groups.values() if len(group) > 1]


def shingles(text, window=WINDOW, sample=SAMPLE):
    """What two printings are compared on: hashes of the five-word runs in the article's first
    600 words of 3+ letters, one in four kept by its own hash as keys does, as a sorted array.
    Shorter runs than keys' seven weather OCR errors better. The leakage check reads every run
    of the whole text: window=None, sample=1."""
    text = (text or "") if window is None else (text or "")[:40000]
    words = WORD.findall(text.replace("-\n", "").lower())[:window]
    found = set()
    for i in range(len(words) - SHINGLE + 1):
        run = " ".join(words[i : i + SHINGLE]).encode()
        low = zlib.crc32(run)
        if low % sample == 0:
            found.add(zlib.crc32(run, 0x5BD1E995) << 32 | low)
    return np.array(sorted(found), dtype=np.uint64)


def overlap(a, b):
    """How much two printings share: the shingles they share, and those as a share of the
    shorter's shingles and of the longer's. A cut reprint is held whole in its original, which
    it holds only part of."""
    if not len(a) or not len(b):
        return 0, 0.0, 0.0
    shared = len(np.intersect1d(a, b, assume_unique=True))
    return shared, shared / min(len(a), len(b)), shared / max(len(a), len(b))


def stories(doc_keys, doc_shingles, order, threshold, boilerplate=BOILERPLATE):
    """Printings grouped into stories without chaining (decision 36). Each printing, earliest
    first (`order`), looks at the stories of the printings it shares a pair of runs with, as
    `clusters` links them. It joins the story whose first printing it matches best, where at
    least `threshold` of the shorter's shingles are the other's; otherwise it starts a story
    of its own. Returns each document's story, as the index of its first printing, and its
    match to that printing (1.0 for a first printing)."""
    assert len(doc_keys) < 1 << DOC_BITS
    mask = (1 << DOC_BITS) - 1
    entries = sorted(
        key << DOC_BITS | doc
        for doc, held in enumerate(doc_keys)
        for key in pairs(held)
    )
    links = [[] for _ in doc_keys]  # each document's shared pairs of runs, by number
    shared, start = 0, 0
    for end in range(1, len(entries) + 1):
        if (
            end < len(entries)
            and entries[end] >> DOC_BITS == entries[start] >> DOC_BITS
        ):
            continue
        if 2 <= end - start <= boilerplate:
            for entry in entries[start:end]:
                links[entry & mask].append(shared)
            shared += 1
        start = end
    rank = {doc: i for i, doc in enumerate(order)}
    seen = [
        [] for _ in range(shared)
    ]  # the stories of the printings seen with each pair
    story, match = list(range(len(doc_keys))), [1.0] * len(doc_keys)
    for doc in order:
        best, score = doc, 0.0
        heard = {first for pair in links[doc] for first in seen[pair]}
        for first in sorted(heard, key=rank.__getitem__):
            of_shorter = overlap(doc_shingles[doc], doc_shingles[first])[1]
            if of_shorter >= threshold and of_shorter > score:
                best, score = first, of_shorter
        story[doc] = best
        match[doc] = score if best != doc else 1.0
        for pair in links[doc]:
            if best not in seen[pair]:
                seen[pair].append(best)
    return story, match
