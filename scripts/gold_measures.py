"""What the frozen gold labels measure (2C.2), written to eval/results/phase2c/gold_measures.json:

- reports in each stratum and in all, beside the draw's expectation (decision 37)
- the weighted report rate, sum(w * report) / sum(w), with a stratified bootstrap interval
- the story-place rule (POLICY.md) as code, scored against the labelled place_state, beside
  the paper's state that decision 34's fallback would have given
- each edge-case slice's count in gold and dev, with E9 from the inclusive grouping

A label is the ruling where the two passes disagreed, and the first pass's where they agreed.

The story-place rule, as code, for a report's place:
  1. a state named after a comma in the place's quote: "Sharpsburg, Md"
  2. else a town of the quote named elsewhere with a state after a comma: "Sharpsburg, Md."
  3. else the dateline's state: "Albia, Ia., Sept. 19"
  4. else none; the paper's state is never taken
"""

import json
import random
import re
from collections import Counter
from pathlib import Path

from check_leakage import SPLIT, frame
from label_gold import OUT, ROOT, articles, saved, squeezed
from second_pass import FIRST

from paperghosts.geo.loc import CACHE, recorded
from paperghosts.geo.papers import modern_state
from paperghosts.geo.titles import STATES, key, parse_title, state_name
from paperghosts.stats import wilson

RULING = "ruling"
DRAW = ROOT / "eval" / "results" / "phase2c" / "gold_draw.json"
RESULT = ROOT / "eval" / "results" / "phase2c" / "gold_measures.json"
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b"
DATELINE = re.compile(
    rf"[A-Z][\w'&-]*(?:\s+[A-Z][\w'&-]*)*\s*[,.]+\s*([A-Za-z][A-Za-z. ]{{0,16}}?)\s*[,.]+\s*{MONTH}"
)
TOWN = re.compile(r"\b[A-Z][a-z]{2,}\b")
LCCN = re.compile(r"_(sn\d+)_")


def stated(after: str) -> str | None:
    """The state that text after a comma begins with, in one to three words."""
    words = after.split()[:3]
    for n in range(len(words), 0, -1):
        found = STATES.get(key(" ".join(words[:n])))
        if found:
            return found
    return None


def story_state(text: str, place: dict) -> str | None:
    """The state the story-place rule gives a report's place, from its text alone."""
    quote = squeezed(place["quote"])
    for after in quote.split(",")[1:]:
        if found := stated(after):
            return found
    for town in TOWN.findall(quote):
        for hit in re.finditer(rf"\b{re.escape(town)}\s*,", text):
            if found := stated(text[hit.end() : hit.end() + 30]):
                return found
    dateline = DATELINE.search(text[:300])
    return STATES.get(key(dateline[1])) if dateline else None


def paper_state(row: dict, cache: Path = CACHE) -> str | None:
    """The state the paper's printed title gives, or its cached title record's."""
    found = modern_state(parse_title((row.get("paper") or "").split(" · ")[0]))
    lccn = LCCN.search(row.get("article_id") or "")
    if found or not lccn or not (cache / f"{lccn[1]}.json").exists():
        return found
    record = recorded(json.loads((cache / f"{lccn[1]}.json").read_text()))
    return state_name(record["states"][0]) if record and record["states"] else None


def final(records: list) -> dict:
    """Each article's final label: the ruling where there is one, else the first pass's."""
    found = {}
    for record in records:
        if record["labeller"] == RULING or (
            record["labeller"] == FIRST and record["article_id"] not in found
        ):
            found[record["article_id"]] = record
    return found


def by_stratum(items: list, kinds: dict, expected: dict) -> dict:
    """Gold's reports in each stratum and in all, beside the draw's expected reports."""
    strata = {}
    for item in items:
        row = strata.setdefault(item["stratum"], {"gold": 0, "reports": 0})
        row["gold"] += 1
        row["reports"] += kinds[item["article_id"]] == "report"
    for name, row in strata.items():
        row["expected"] = expected["strata"][name]["reports"]
    return {
        "strata": strata,
        "total": {
            "gold": len(items),
            "reports": sum(r["reports"] for r in strata.values()),
            "expected": expected["total"],
        },
    }


def weighted(items: list, kinds: dict, draws: int = 2000) -> dict:
    """The weighted report rate, with a 95% percentile interval from resampling each stratum."""

    def rate(drawn):
        return sum(
            i["weight"] * (kinds[i["article_id"]] == "report") for i in drawn
        ) / sum(i["weight"] for i in drawn)

    strata = {}
    for item in items:
        strata.setdefault(item["stratum"], []).append(item)
    rng, found = random.Random("2C.2 weighted rate bootstrap"), []
    for _ in range(draws):
        found.append(rate([rng.choice(part) for part in strata.values() for _ in part]))
    found.sort()
    return {
        "rate": rate(items),
        "interval": [found[int(0.025 * draws)], found[int(0.975 * draws) - 1]],
    }


def e9(grouping: dict, ids: list) -> set:
    """The articles whose group in the inclusive grouping has another member: E9's reprints."""
    sizes = Counter(grouping["group"])
    group = dict(zip(grouping["ids"], grouping["group"], strict=True))
    return {aid for aid in ids if sizes[group[aid]] > 1}


def places(reports: dict, rows: dict) -> dict:
    """The story-place rule against the labelled place_state, on gold's reports with a place,
    and the paper's state where the label has one."""
    cases, wrong, paper = Counter(), [], Counter()
    for aid, label in sorted(reports.items()):
        if not label.get("place"):
            continue
        row = rows[aid]
        text = squeezed(f"{row.get('headline') or ''}\n{row.get('text') or ''}")
        rule, labelled = (
            story_state(text, label["place"]),
            (label.get("place_state") or {}).get("value"),
        )
        case = (
            ("both empty" if not rule else "same")
            if rule == labelled
            else "missed"
            if not rule
            else "extra"
            if not labelled
            else "wrong"
        )
        cases[case] += 1
        if case not in ("same", "both empty"):
            wrong.append(
                {"article_id": aid, "rule": rule, "labelled": labelled, "case": case}
            )
        if labelled:
            paper[paper_state(row) == labelled] += 1
    n, agree = sum(cases.values()), cases["same"] + cases["both empty"]
    return {
        "places": n,
        "agree": agree,
        "rate": agree / n,
        "interval": wilson(agree, n),
        "cases": dict(cases),
        "disagreements": wrong,
        "paper_state": {
            "labelled_states": paper[True] + paper[False],
            "paper_same": paper[True],
            "interval": wilson(paper[True], paper[True] + paper[False]),
        },
    }


def main() -> None:
    split = json.loads(SPLIT.read_text())
    labels = {name: final(saved(OUT[name])) for name in OUT}
    kinds = {aid: label["kind"] for aid, label in labels["gold"].items()}
    rows = articles()
    grouped = e9(frame(ROOT), [i["article_id"] for name in OUT for i in split[name]])
    slices = {
        name: dict(
            sorted(
                Counter(
                    s
                    for aid, label in labels[name].items()
                    for s in [*label["slices"], *(["E9"] if aid in grouped else [])]
                ).items(),
                key=lambda kv: int(kv[0][1:]),
            )
        )
        for name in OUT
    }
    reports = {
        aid: label for aid, label in labels["gold"].items() if label["kind"] == "report"
    }
    found = {
        "reports": by_stratum(
            split["gold"], kinds, json.loads(DRAW.read_text())["expected_reports"]
        ),
        "weighted_report_rate": weighted(split["gold"], kinds),
        "story_place_rule": places(reports, rows),
        "slices": slices,
        "e9": sorted(grouped),
    }
    RESULT.write_text(json.dumps(found, indent=1) + "\n")
    print(json.dumps({k: v for k, v in found.items() if k not in ("e9",)}, indent=1))


if __name__ == "__main__":
    main()
