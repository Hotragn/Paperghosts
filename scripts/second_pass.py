"""The blind second pass over the gold and dev labels (2C.2).

Every gold article and a seeded fifth of dev are labelled again by readers who see only the
text, its crops and POLICY.md: no first label, stratum or weight. Their labels go to
eval/gold/second_pass.jsonl as labeller "second pass", never into the label files the evals
read, and the two passes' agreement is measured before any ruling. Each ruling replaces its
article's label in labels.jsonl or dev_labels.jsonl, and eval/gold/adjudication.jsonl keeps
the first label, the second, the ruling and its reason. So the label files hold one label per
article: the first pass's where the passes agreed, the ruling where they didn't.

  packets K DIR      the pass's articles in K packets of text, each with its texts for check
  check FILE TEXTS   a packet's labels through checked(), against its texts alone
  save FILE          a packet's labels through checked(), into second_pass.jsonl
  agreement          the agreement, with 95% intervals, into eval/results/phase2c/agreement.json
  disputes           every article the passes disagree on, as JSON lines, for a ruling
  rule FILE          rulings ({"label": ..., "reason": ...} per line) on disputed articles
  frozen             each label file's count, labellers, checked() and sha256

A field agrees when both passes leave it empty, or:
  outcome, place_type, precision, place_state   they give the same value
  place, seen, specific_place                   their quotes overlap in the text, or their
                                                values are the same, ignoring case
  people                                        each person's quote overlaps one of the
                                                other pass's, both ways
"""

import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

from label_gold import (
    FIELDS,
    OUT,
    ROOT,
    SEEN,
    articles,
    checked,
    save,
    save_file,
    saved,
    shown,
    squeezed,
)

from paperghosts.stats import wilson

DEV_SHARE = 0.2
FIRST, SECOND, RULING = "Claude", "second pass", "ruling"
SECOND_PASS = ROOT / "eval" / "gold" / "second_pass.jsonl"
ADJUDICATION = ROOT / "eval" / "gold" / "adjudication.jsonl"
RESULT = ROOT / "eval" / "results" / "phase2c" / "agreement.json"
VALUES = {"outcome", "place_type", "precision", "place_state"}


def sampled(dev: list, share: float = DEV_SHARE) -> list:
    """The seeded share of dev that the second pass labels again."""
    ids = sorted(dev)
    return sorted(
        random.Random("2C.2 second pass dev sample").sample(
            ids, round(len(ids) * share)
        )
    )


def passed(rows: dict) -> list:
    """Every gold article and the dev sample, in one seeded shuffle, so a packet doesn't show
    which split an article is from."""
    gold = sorted(aid for aid, row in rows.items() if row["split"] == "gold")
    dev = [aid for aid, row in rows.items() if row["split"] == "dev"]
    order = gold + sampled(dev)
    random.Random("2C.2 second pass order").shuffle(order)
    return order


def packets(rows: dict, ids: list, k: int, cropped: dict) -> list:
    """The ids in k packets of near-equal size: each packet's text to read, and the headline
    and text of its articles, all that checked() needs."""
    size, extra = divmod(len(ids), k)
    made, start = [], 0
    for i in range(k):
        part = ids[start : start + size + (i < extra)]
        start += len(part)
        texts = {
            aid: {"headline": rows[aid].get("headline"), "text": rows[aid].get("text")}
            for aid in part
        }
        made.append(
            ("\n\n".join(shown(aid, rows[aid], cropped) for aid in part), texts)
        )
    return made


def kappa(a: list, b: list) -> float | None:
    """Cohen's kappa for two raters' categories; None when chance agreement is certain."""
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    chance = sum((a.count(c) / n) * (b.count(c) / n) for c in set(a) | set(b))
    return None if chance == 1 else (observed - chance) / (1 - chance)


def interval(a: list, b: list, draws: int = 2000) -> list | None:
    """A 95% percentile bootstrap interval for kappa, resampling articles."""
    rng, n, found = random.Random("2C.2 kappa bootstrap"), len(a), []
    for _ in range(draws):
        picks = [rng.randrange(n) for _ in range(n)]
        value = kappa([a[i] for i in picks], [b[i] for i in picks])
        if value is not None:
            found.append(value)
    if not found:
        return None
    found.sort()
    return [
        found[int(0.025 * len(found))],
        found[min(len(found) - 1, int(0.975 * len(found)))],
    ]


def spans(quote: str, text: str) -> list:
    needle, found, at = squeezed(quote), [], text.find(squeezed(quote))
    while needle and at >= 0:
        found.append((at, at + len(needle)))
        at = text.find(needle, at + 1)
    return found


def overlap(a: dict, b: dict, text: str) -> bool:
    if a["value"].casefold() == b["value"].casefold():
        return True
    return any(
        s < f and t < e
        for s, e in spans(a["quote"], text)
        for t, f in spans(b["quote"], text)
    )


def same(name: str, a: dict, b: dict, text: str) -> bool:
    """Whether the two passes agree on one field of a report; the module's docstring says how."""
    if name == "people":
        first, second = a.get("people") or [], b.get("people") or []
        return all(any(overlap(p, q, text) for q in second) for p in first) and all(
            any(overlap(q, p, text) for p in first) for q in second
        )
    x, y = a.get(name), b.get(name)
    if not x or not y:
        return not x and not y
    return x["value"] == y["value"] if name in VALUES else overlap(x, y, text)


def rate(agree: int, n: int) -> dict:
    return {"agree": agree, "n": n, "rate": agree / n, "interval": wilson(agree, n)}


def agreed(pairs: list, texts: dict) -> dict:
    """Kind, report-or-not and each field, on the pairs both passes call reports."""
    kinds = [(a["kind"], b["kind"]) for a, b in pairs]
    reports = [(a["kind"] == "report", b["kind"] == "report") for a, b in pairs]
    both = [(a, b) for a, b in pairs if a["kind"] == b["kind"] == "report"]
    found = {"n": len(pairs)}
    for name, values in (("kind", kinds), ("report", reports)):
        first, second = [x for x, _ in values], [y for _, y in values]
        found[name] = rate(sum(x == y for x, y in values), len(values)) | {
            "kappa": kappa(first, second),
            "kappa_interval": interval(first, second),
        }
    found["fields"] = {
        name: rate(
            sum(same(name, a, b, texts[a["article_id"]]) for a, b in both), len(both)
        )
        for name in (*FIELDS, "people")
        if both
    }
    return found


def disputes(pairs: list, texts: dict) -> list:
    """Each article the passes disagree on: its kinds, and the fields of a report both call one."""
    found = []
    for a, b in pairs:
        fields = (
            [
                name
                for name in (*FIELDS, "people")
                if not same(name, a, b, texts[a["article_id"]])
            ]
            if a["kind"] == b["kind"] == "report"
            else []
        )
        if a["kind"] != b["kind"] or fields:
            found.append(
                {
                    "article_id": a["article_id"],
                    "kinds": [a["kind"], b["kind"]],
                    "fields": fields,
                }
            )
    return found


def paired(
    split: str, out=OUT, second_pass=SECOND_PASS, adjudication=ADJUDICATION
) -> list:
    """The first and second passes' labels of each article both labelled, in article order.
    A ruled article's first label is the one adjudication.jsonl kept."""
    first = {r["article_id"]: r for r in saved(out[split])}
    first |= {
        a["article_id"]: a["first"]
        for a in saved(adjudication)
        if a["article_id"] in first
    }
    second = {
        r["article_id"]: r for r in saved(second_pass) if r["article_id"] in first
    }
    return [(first[aid], second[aid]) for aid in sorted(second)]


def rule(
    rulings: list,
    rows: dict,
    texts: dict,
    out=OUT,
    second_pass=SECOND_PASS,
    adjudication=ADJUDICATION,
) -> list:
    """Each ruling, through checked(), replacing its disputed article's label; returns what
    adjudication.jsonl keeps for it: both passes' labels, the ruling and its reason."""
    both = [p for name in out for p in paired(name, out, second_pass, adjudication)]
    disputed = {d["article_id"]: d for d in disputes(both, texts)}
    pairs = {a["article_id"]: (a, b) for a, b in both}
    kept = []
    for given in rulings:
        aid = given["label"]["article_id"]
        if aid not in disputed:
            raise ValueError(f"{aid}: not a disputed article")
        record = checked(given["label"], rows[aid], RULING)
        record["note"] = f"ruling: {given['reason']}"
        first, second = pairs[aid]
        kept.append(
            {
                **disputed[aid],
                "first": first,
                "second": second,
                "ruling": record,
                "reason": given["reason"],
            }
        )
        save(out[rows[aid]["split"]], record, replace=True)
    return kept


def main() -> None:
    run, *rest = sys.argv[1:]
    if run == "check":
        path, given = map(Path, rest)
        texts = json.loads(given.read_text())
        errors = []
        for line in filter(str.strip, path.read_text().splitlines()):
            label = json.loads(line)
            row = texts.get(label.get("article_id"))
            try:
                if row is None:
                    raise ValueError("not an article in this packet")
                checked(label, {"article_id": label["article_id"], **row}, SECOND)
            except ValueError as error:
                errors.append(f"{label.get('article_id')}: {error}")
        print("\n".join(errors) or "every label passes checked()")
        sys.exit(1 if errors else 0)
    rows = articles()
    if run == "save":
        errors = save_file(
            Path(rest[0]), rows, SECOND, out={"gold": SECOND_PASS, "dev": SECOND_PASS}
        )
        print("\n".join(errors) or "every label passes checked()")
        sys.exit(1 if errors else 0)
    if run == "frozen":
        for name, path in OUT.items():
            records = saved(path)
            ids = {r["article_id"] for r in records}
            wanted = {aid for aid, row in rows.items() if row["split"] == name}
            failed = [
                r["article_id"] for r in records if not passes(r, rows[r["article_id"]])
            ]
            print(
                json.dumps(
                    {
                        "file": path.name,
                        "labels": len(records),
                        "articles": len(ids),
                        "the_split_exactly": ids == wanted
                        and len(records) == len(wanted),
                        "labellers": dict(Counter(r["labeller"] for r in records)),
                        "failing_checked": failed,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
            )
        return
    if run == "packets":
        k, out = int(rest[0]), Path(rest[1])
        cropped = json.loads(SEEN.read_text())
        out.mkdir(parents=True, exist_ok=True)
        for i, (text, texts) in enumerate(packets(rows, passed(rows), k, cropped), 1):
            (out / f"packet{i:02}.txt").write_text(text + "\n")
            (out / f"texts{i:02}.json").write_text(json.dumps(texts) + "\n")
        return
    texts = {
        aid: squeezed(f"{row.get('headline') or ''}\n{row.get('text') or ''}")
        for aid, row in rows.items()
    }
    gold, dev = paired("gold"), paired("dev")
    if run == "agreement":
        found = {
            name: agreed(pairs, texts)
            for name, pairs in (("gold", gold), ("dev", dev), ("all", gold + dev))
        }
        RESULT.write_text(json.dumps(found, indent=1) + "\n")
        print(
            json.dumps(
                {
                    name: {k: v for k, v in part.items() if k != "fields"}
                    for name, part in found.items()
                },
                indent=1,
            )
        )
    elif run == "disputes":
        ruled = {a["article_id"] for a in saved(ADJUDICATION)}
        for item in disputes(gold + dev, texts):
            print(json.dumps(item | {"ruled": item["article_id"] in ruled}))
    elif run == "rule":
        given = [
            json.loads(line)
            for line in Path(rest[0]).read_text().splitlines()
            if line.strip()
        ]
        kept = {a["article_id"]: a for a in saved(ADJUDICATION)}
        kept |= {a["article_id"]: a for a in rule(given, rows, texts)}
        ADJUDICATION.write_text(
            "".join(json.dumps(kept[aid]) + "\n" for aid in sorted(kept))
        )
        print(len(given), "rulings;", len(kept), "in adjudication.jsonl")


def passes(record: dict, row: dict) -> bool:
    """Whether a saved label still passes checked() as its labeller saved it."""
    try:
        return checked(record, row, record["labeller"])["kind"] == record["kind"]
    except ValueError:
        return False


if __name__ == "__main__":
    main()
