"""Reprint clusters, for eval A's reprint signal: a syndicated story was printed in many
papers in the same words, give or take OCR errors, so articles that share a run of words are
taken for printings of one story."""

import re
import zlib

WORD = re.compile(r"[a-z]{3,}")
RUN, OPENING, ONE_IN = 7, 120, 8  # words per run, words read, one run kept in ONE_IN
BOILERPLATE = 1000  # a run more articles than this share is stock phrasing, not a story
DOC_BITS = 21  # room for 2 million documents beside each key
SKETCH = 6  # the smallest keys a document is paired on
MASK64 = (1 << 64) - 1


def keys(text):
    """64-bit hashes of a sample of the seven-word runs in the article's opening. A run is
    kept by its own hash, so the sample doesn't shift when one printing has an extra line."""
    words = WORD.findall((text or "")[:6000].replace("-\n", "").lower())[:OPENING]
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
