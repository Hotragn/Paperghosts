"""Independent blind rulings on the second pass's disputes (decision 38's review).

The rulings in adjudication.jsonl were made by the first labeller. Here fresh readers rule on
every dispute again, one pair at a time. Each sees POLICY.md, the article and its crops, and
the two labels as A and B in a seeded order, with no labeller's name, note or ruling. Their
rulings are then compared with adjudication.jsonl's.

  packets K DIR      the disputes in K packets of text, with the A/B key kept apart in DIR/key.json
  check FILE TEXTS   a judge's rulings: every case once, and every quote in its case's text
  compare FILE KEY   the independent rulings against adjudication.jsonl's, with Wilson intervals,
                     into eval/results/phase2c/blind_rulings.json
"""

import json
import random
import sys
from pathlib import Path

from label_gold import FIELDS, ROOT, SEEN, articles, saved, shown, squeezed
from second_pass import ADJUDICATION, same

from paperghosts.stats import wilson

RESULT = ROOT / "eval" / "results" / "phase2c" / "blind_rulings.json"
SHOWN = ("kind", "kind_quote", *FIELDS, "people")


def masked(label: dict) -> dict:
    """A label as a blind judge sees it: its kind, quotes and fields, and nothing of who made
    it or why."""
    return {k: label.get(k) for k in SHOWN if label.get(k) not in (None, [])}


def cases(disputed: list) -> tuple[list, dict]:
    """Each dispute as a case, in one seeded order, its two labels as A and B by a seeded coin;
    and the key saying which pass each letter is."""
    rng = random.Random("2C.2 blind rulings")
    order = sorted(disputed, key=lambda d: d["article_id"])
    rng.shuffle(order)
    made, key = [], {}
    for i, d in enumerate(order, 1):
        case = f"c{i:02}"
        first_is_a = rng.random() < 0.5
        a, b = (d["first"], d["second"]) if first_is_a else (d["second"], d["first"])
        key[case] = {
            "article_id": d["article_id"],
            "A": "first" if first_is_a else "second",
        }
        made.append(
            {
                "case": case,
                "article_id": d["article_id"],
                "disputed": ["kind"] * (d["kinds"][0] != d["kinds"][1]) + d["fields"],
                "A": masked(a),
                "B": masked(b),
            }
        )
    return made, key


def stated(value):
    """A judge's field value as a label holds it: {value, quote}, a list of people, or None."""
    if isinstance(value, list):
        return [p for p in value if p and p.get("value")]
    return value if value and value.get("value") else None


def compared(rulings: list, key: dict, disputed: dict, texts: dict) -> dict:
    """How often the blind rulings match adjudication.jsonl's, per kind and per field, and how
    often each pass's label won, with Wilson intervals."""
    match, won = {}, {}
    for given in rulings:
        case = key[given["case"]]
        d = disputed[case["article_id"]]
        text = texts[case["article_id"]]
        sides = {"first": d["first"], "second": d["second"]}
        if d["kinds"][0] != d["kinds"][1]:
            kind = given["kind"]
            match.setdefault("kind", []).append(kind == d["ruling"]["kind"])
            side = next(
                (s for s, lab in sides.items() if lab["kind"] == kind), "neither"
            )
            won.setdefault("kind", []).append(side)
        for name in d["fields"]:
            if name not in given.get("fields", {}):
                continue
            mine = {name: d["ruling"].get(name)}
            theirs = {name: stated(given["fields"][name])}
            match.setdefault(name, []).append(same(name, mine, theirs, text))
            side = next(
                (
                    s
                    for s, lab in sides.items()
                    if same(name, {name: lab.get(name)}, theirs, text)
                ),
                "neither",
            )
            won.setdefault(name, []).append(side)
    return {
        name: {
            "agree": sum(hits),
            "n": len(hits),
            "rate": sum(hits) / len(hits),
            "interval": wilson(sum(hits), len(hits)),
            "won": {s: won[name].count(s) for s in ("first", "second", "neither")},
        }
        for name, hits in match.items()
    }


def problems(rulings: list, texts: dict) -> list:
    """What's wrong with a judge's rulings: a case missing or repeated, or a quote not in the text."""
    found = [
        f"{c}: no ruling"
        for c in texts
        if sum(r.get("case") == c for r in rulings) != 1
    ]
    for r in rulings:
        text = squeezed(
            f"{texts[r['case']]['headline'] or ''}\n{texts[r['case']]['text'] or ''}"
        )
        quotes = [r.get("kind_quote")] + [
            p.get("quote")
            for v in (r.get("fields") or {}).values()
            for p in (v if isinstance(v, list) else [v])
            if p
        ]
        found += [
            f"{r['case']}: quote not in the text: {q!r}"
            for q in quotes
            if q and squeezed(q) not in text
        ]
    return found


def main() -> None:
    run, *rest = sys.argv[1:]
    if run == "check":
        rulings = [
            json.loads(line)
            for line in Path(rest[0]).read_text().splitlines()
            if line.strip()
        ]
        errors = problems(rulings, json.loads(Path(rest[1]).read_text()))
        print("\n".join(errors) or "every ruling checks")
        sys.exit(1 if errors else 0)
    disputed = {d["article_id"]: d for d in saved(ADJUDICATION)}
    if run == "packets":
        k, out = int(rest[0]), Path(rest[1])
        rows, cropped = articles(), json.loads(SEEN.read_text())
        made, key = cases(list(disputed.values()))
        out.mkdir(parents=True, exist_ok=True)
        (out / "key.json").write_text(json.dumps(key, indent=1) + "\n")
        size, extra = divmod(len(made), k)
        start = 0
        for i in range(k):
            part = made[start : start + size + (i < extra)]
            start += len(part)
            text = "\n\n".join(
                f"##### {c['case']}  disputed: {', '.join(c['disputed'])}\n"
                + shown(
                    c["case"],
                    dict(rows[c["article_id"]], paper="", date=""),
                    {c["case"]: cropped.get(c["article_id"], {})},
                )
                + f"\n--- A: {json.dumps(c['A'], ensure_ascii=False)}\n--- B: {json.dumps(c['B'], ensure_ascii=False)}"
                for c in part
            )
            (out / f"cases{i + 1:02}.txt").write_text(text + "\n")
            texts = {
                c["case"]: {
                    "headline": rows[c["article_id"]].get("headline"),
                    "text": rows[c["article_id"]].get("text"),
                }
                for c in part
            }
            (out / f"texts{i + 1:02}.json").write_text(json.dumps(texts) + "\n")
    elif run == "compare":
        rulings = [
            json.loads(line)
            for line in Path(rest[0]).read_text().splitlines()
            if line.strip()
        ]
        key = json.loads(Path(rest[1]).read_text())
        rows = articles()
        texts = {
            aid: squeezed(f"{r.get('headline') or ''}\n{r.get('text') or ''}")
            for aid, r in rows.items()
            if aid in disputed
        }
        found = compared(rulings, key, disputed, texts)
        RESULT.write_text(json.dumps(found, indent=1) + "\n")
        print(json.dumps(found, indent=1))


if __name__ == "__main__":
    main()
