"""RDR-4's check: a pool article that reprints a gold or dev article leaks, judged on whole
texts; a shared stock phrase or a quoted paragraph doesn't. A group of the inclusive grouping
that spans the split fails it."""

import hashlib
import json

import check_leakage
import zstandard
from check_leakage import between, crossings, flagged, hashes_hold, leaks, runs

STORY = " ".join(
    f"word{chr(97 + i % 26)}{chr(97 + i // 26 % 26)}{chr(97 + i // 676)}"
    for i in range(300)
)
OTHER = " ".join(
    f"other{chr(97 + i % 26)}{chr(97 + i // 26 % 26)}{chr(97 + i // 676)}"
    for i in range(300)
)


def test_a_reprint_shares_enough_of_the_shorters_runs_and_a_quotation_doesnt():
    words = STORY.split()
    cut = " ".join(words[:60])  # the story cut short, as a reprint often is
    quoted = " ".join(OTHER.split()[:150] + words[100:115] + OTHER.split()[150:])

    assert len(runs(STORY)) == 296 and flagged(56, len(runs(cut)), 296)
    assert between({"story": STORY}, {"cut": cut, "other": OTHER}) == [("story", "cut")]
    # a quoted paragraph of 15 words: 11 runs, past FEWEST but under LEAK of the shorter
    assert between({"story": STORY}, {"quoted": quoted}) == []
    assert not flagged(4, 4, 296)  # a stock phrase or two: too few runs, however short


def test_the_pool_scan_finds_a_reprint_outside_the_excluded_and_skips_the_random_reservoir(
    tmp_path, monkeypatch
):
    rows = {
        "candidates": [
            {"article_id": "reprint", "text": "From the Courant. " + STORY},
            {"article_id": "unrelated", "text": OTHER},
            {"article_id": "gold's own group", "text": STORY},
        ],
        "samples": [
            {"article_id": "random one", "sample": "random", "text": STORY},
            {"article_id": "near miss", "sample": "near_miss", "text": STORY[:900]},
        ],
    }
    for folder, items in rows.items():
        (tmp_path / "data" / folder).mkdir(parents=True)
        with zstandard.open(tmp_path / "data" / folder / "1890.jsonl.zst", "wt") as f:
            f.writelines(json.dumps(item) + "\n" for item in items)
    monkeypatch.setattr(check_leakage, "ROOT", tmp_path)

    found = leaks(tmp_path, {"gold": STORY}, excluded={"gold's own group"}, workers=1)

    assert sorted((pool, held) for pool, held, *_ in found) == [
        ("near miss", "gold"),
        ("reprint", "gold"),
    ]


def test_a_group_that_holds_gold_and_the_pool_or_gold_and_dev_crosses_the_split():
    found = {
        "ids": ["g", "g's reprint", "d", "d's reprint", "q", "q's reprint", "free"],
        "group": ["g", "g", "g", "d", "q", "q", "free"],
    }

    # g's reprint is held out, but d sits in g's group, and q's reprint is still in the pool
    assert crossings(
        found,
        gold={"g"},
        dev={"d"},
        held={"g", "d", "q"},
        out={"g's reprint", "d's reprint"},
    ) == ["g", "q"]
    assert (
        crossings(
            found,
            gold={"g"},
            dev=set(),
            held={"g", "q"},
            out={"g's reprint", "d", "d's reprint", "q's reprint"},
        )
        == []
    )


def test_hash_lists_its_files_by_name_and_each_must_match(tmp_path):
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    (tmp_path / "split.json").write_text("{}")
    (tmp_path / "labels.jsonl").write_text("a\n")
    listed = tmp_path / "HASH"
    listed.write_text(
        f"{sha(tmp_path / 'split.json')}  split.json\n"
        f"{sha(tmp_path / 'labels.jsonl')}  labels.jsonl\n"
    )
    assert hashes_hold(listed)

    (tmp_path / "labels.jsonl").write_text("b\n")
    assert not hashes_hold(listed)
    listed.write_text(f"{sha(tmp_path / 'labels.jsonl')}  labels.jsonl\n")
    assert not hashes_hold(listed)  # split.json must be among them
