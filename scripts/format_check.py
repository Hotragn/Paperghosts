"""A teacher's misses on dev's choice fields, sorted into format, verifier and judgment (2C.3).

On the reports both dev and the teacher call reports, each choice field the teacher gets wrong after
the verifier is put in one class:
  format     the answer gave the field as a bare string instead of {"value", "quote"}, or gave a
             value outside the schema (a choice not in CHOICES, a place_state that isn't a state)
  verifier   a well-formed value whose quote the verifier dropped
  judgment   a well-formed, verified value that differs from dev's
Each field is then scored again with the format normalised: a bare string that is a schema value is
read as that value, unverified because it has no quote, and a place_state that isn't a state is left
empty. Both scores are kept. The normalisation is for scoring only: a training label goes through
teacher.verified, which drops any value without a verified quote. Reads the saved rounds only.

  uv run python scripts/format_check.py ROUND...
Writes eval/results/phase2c/format_check.json.
"""

import json
import sys

from label_gold import CHOICES, OUT, ROOT, articles, saved, squeezed
from second_pass import VALUES, same
from teacher import RESULTS, parsed, verified

from paperghosts.geo.titles import is_state
from paperghosts.stats import wilson

RESULT = RESULTS / "format_check.json"


def raw_fields(answer: str) -> dict:
    start, end = answer.find("{"), answer.rfind("}")
    try:
        found = json.loads(answer[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return found if isinstance(found, dict) else {}


def in_schema(name: str, value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if name == "place_state":
        return is_state(value)
    return name not in CHOICES or value in CHOICES[name]


def normalised(name: str, given):
    """The field as the schema would have it, or None; a bare string carries no quote."""
    value = given.get("value") if isinstance(given, dict) else given
    if not in_schema(name, value):
        return None
    return {
        "value": value,
        "quote": given.get("quote") if isinstance(given, dict) else "",
    }


def checked(round_name: str, labels: dict, texts: dict, threshold: float) -> dict:
    found = {}
    lines = (
        (ROOT / "data" / "teacher" / f"dev_{round_name}.jsonl").read_text().splitlines()
    )
    for line in lines:
        o = json.loads(line)
        aid, answer = o["article_id"], o.get("answer") or ""
        label, dev = parsed(answer), labels[aid]
        if not label or dev["kind"] != "report" or label["kind"] != "report":
            continue
        kept = verified({**label, "article_id": aid}, texts[aid], threshold)[0]
        raw = raw_fields(answer)
        for name in sorted(VALUES):
            field = found.setdefault(
                name, {"n": 0, "agree": 0, "normalised_agree": 0, "misses": []}
            )
            field["n"] += 1
            given = raw.get(name)
            stated = isinstance(given, dict) and in_schema(name, given.get("value"))
            # only a format failure is normalised; a well-formed value keeps the verifier's ruling
            fixed = kept.get(name) if stated or not given else normalised(name, given)
            field["normalised_agree"] += same(name, dev, {name: fixed}, texts[aid])
            if same(name, dev, kept, texts[aid]):
                field["agree"] += 1
                continue
            if given and not stated:
                kind = "format"
            elif label.get(name) and not kept.get(name):
                kind = "verifier"
            else:
                kind = "judgment"
            field["misses"].append(
                {
                    "article_id": aid,
                    "class": kind,
                    "dev": (dev.get(name) or {}).get("value"),
                    "teacher": given,
                    "right_once_normalised": same(name, dev, {name: fixed}, texts[aid]),
                }
            )
    for field in found.values():
        classes = [m["class"] for m in field["misses"]]
        field |= {
            "interval": wilson(field["agree"], field["n"]),
            "normalised_interval": wilson(field["normalised_agree"], field["n"]),
            "by_class": {
                c: classes.count(c) for c in ("format", "verifier", "judgment")
            },
        }
    return found


def main(rounds: list) -> None:
    rows = {aid: r for aid, r in articles().items() if r["split"] == "dev"}
    labels = {r["article_id"]: r for r in saved(OUT["dev"])}
    texts = {
        aid: squeezed(f"{r.get('headline') or ''}\n{r.get('text') or ''}")
        for aid, r in rows.items()
    }
    found = json.loads(RESULT.read_text()) if RESULT.exists() else {}
    for round_name in rounds:
        scored = json.loads((RESULTS / f"teacher_dev_{round_name}.json").read_text())
        found[round_name] = checked(
            round_name, labels, texts, scored["verifier"]["threshold"]
        )
    RESULT.write_text(json.dumps(found, indent=1) + "\n")
    for round_name in rounds:
        for name, f in found[round_name].items():
            print(
                round_name,
                name,
                f"{f['agree']}/{f['n']}",
                "normalised",
                f"{f['normalised_agree']}/{f['n']}",
                f["by_class"],
            )


if __name__ == "__main__":
    main(sys.argv[1:])
