"""The second half of `make eval`: lexicon v2's read in data/ against v1's, archived in
data/archive/lexicon-v1 (decision 31). It writes eval/results/eval_a_v2/lexicon_v2.json, and the
hand-judged sample of the candidates v2 adds to eval/results/eval_a_v2/added.json.

1. Checks: one code version made the read, every v1 candidate is still one, and every added
   candidate holds only v2's new terms.
2. Each rule's candidates, and the added ones it holds.
3. 200 added candidates at random, judged as in decision 30, and the negatives the readers noted
   as near read in full too: their report rate and the reports v2 gains, overall and by rule.
4. Recall, in-sample: v1's screen (decision 30) read again with v2. v2's terms were chosen from
   that screen's misses, so 2C's eval B gives the independent figure.
"""

import json
import random
import re
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime

import zstandard
from eval_a import DATA, RESULTS, keep_judgments, random_picks, rate, window

from paperghosts.ingest import lexicon

V1 = DATA / "archive" / "lexicon-v1"
OUT = RESULTS / "eval_a_v2"
ADDED = 200


def compare(v1, v2, new):
    """v1's candidates that v2 lost, v2's added ones, and any added one holding an old term."""
    kept = {row["article_id"] for row in v2}
    added = [row for row in v2 if row["article_id"] not in v1]
    return {
        "missing": sorted(v1 - kept),
        "added": added,
        "old_terms": [row["article_id"] for row in added if set(row["terms"]) - new],
    }


def summarise_rules(sample, holding, alone, total):
    """Each rule's share of the judged sample, its report rate, and the reports it gains among
    the added candidates holding it; a rule with no report in its share is flagged. Then its
    marginal yield, the reports only it catches: over the whole sample, and over its sampled
    articles that hold no other term."""
    judged = [s for s in sample if s["ghost_report"] is not None]
    out = {}
    for rule, held in holding.items():
        mine = [s for s in judged if rule in s["terms"]]
        only = [s for s in mine if len(s["terms"]) == 1]
        found = sum(bool(s["ghost_report"]) for s in mine)
        caught = sum(bool(s["ghost_report"]) for s in only)
        out[rule] = {"added": held, "n": len(mine), "no_report": not found}
        if mine:
            out[rule] |= rate(found, len(mine), held)
        out[rule]["marginal"] = rate(caught, len(judged), total)
        if only:
            out[rule]["only"] = {"added": alone[rule]} | rate(
                caught, len(only), alone[rule]
            )
    return out


def recall_in_sample(v1, gained, missed):
    """v2's recall: the reports in v1's candidates and in those v2 adds, over those and the
    reports still missed. The floor takes the most missed, at each end of the found."""
    found = {
        name: v1[f"implied{end}"] + gained[f"implied{end}"]
        for name, end in (("low", "_low"), ("point", ""), ("high", "_high"))
    }
    return {
        "point": found["point"] / (found["point"] + missed["implied"]),
        "at_least": {
            name: f / (f + missed["implied_high"]) for name, f in found.items()
        },
    }


def year_compare(job):
    year, new = job
    with zstandard.open(V1 / "candidates" / f"{year}.jsonl.zst", "rt") as rows:
        v1 = {json.loads(row)["article_id"] for row in rows}
    with zstandard.open(DATA / "candidates" / f"{year}.jsonl.zst", "rt") as rows:
        v2 = [
            {"article_id": row["article_id"], "terms": sorted(row["terms"])}
            for row in map(json.loads, rows)
        ]
    found = compare(v1, v2, new)
    found["added"] = [(year, row["article_id"], row["terms"]) for row in found["added"]]
    return year, len(v1), len(v2), found


def year_items(job):
    """The picked added candidates of one year, as they are judged: the opening, and the text
    around each word of their terms."""
    year, wanted = job
    items = []
    with zstandard.open(DATA / "candidates" / f"{year}.jsonl.zst", "rt") as rows:
        for row in map(json.loads, rows):
            if row["article_id"] not in wanted:
                continue
            text = (row["text"] or "").replace("-\n", "")
            forms = {form for found in row["terms"].values() for form in found}
            spots = sorted(
                {
                    m.start()
                    for f in forms
                    for m in re.finditer(re.escape(f), text, re.IGNORECASE)
                }
            )
            items.append(
                {
                    "article_id": row["article_id"],
                    "year": year,
                    "date": row["date"],
                    "paper": row["paper"],
                    "terms": sorted(row["terms"]),
                    "forms": sorted(forms),
                    "words": len(text.split()),
                    "headline": " / ".join((row["headline"] or "").split("\n"))[:200],
                    "opening": " ".join(text[:420].split()),
                    "contexts": [window(text, p, 300) for p in spots[:6]],
                    "first": None,
                    "rejudged": None,
                    "ghost_report": None,
                    "note": None,
                }
            )
    return items


def year_rescreen(job):
    """Which of v1's screened articles of one year lexicon v2 makes candidates."""
    year, wanted = job
    caught, seen = {}, 0
    with zstandard.open(V1 / "samples" / f"{year}.jsonl.zst", "rt") as rows:
        for row in map(json.loads, rows):
            if row["sample"] != "random":
                continue
            seen += 1
            if seen - 1 in wanted:
                terms = lexicon.ghost_terms(
                    f"{row['headline'] or ''}\n{row['text'] or ''}"
                )
                if terms:
                    caught[row["article_id"]] = sorted(terms)
    return caught


def counts_of(data):
    return {
        c["year"]: c
        for c in (json.loads(p.read_text()) for p in (data / "counts").glob("*.json"))
    }


def main():
    v1_counts, v2_counts = counts_of(V1), counts_of(DATA)
    years = sorted(v2_counts)
    old = {term for c in v1_counts.values() for term in c["by_term"]}
    new = [t for t in (*lexicon.GHOST, *lexicon.TOGETHER) if t not in old]
    manifests = [json.loads(p.read_text()) for p in (DATA / "manifests").glob("*.json")]

    added, missing, old_terms, sizes = [], [], [], Counter()
    with ProcessPoolExecutor(max_workers=6) as pool:
        jobs = [
            (y, set(new))
            for y in sorted(years, key=lambda y: -v2_counts[y]["articles"])
        ]
        for _, n1, n2, found in pool.map(year_compare, jobs):
            sizes.update(v1=n1, v2=n2)
            added += found["added"]
            missing += found["missing"]
            old_terms += found["old_terms"]
    added.sort()
    holding = Counter(term for *_, terms in added for term in terms)
    alone = Counter(terms[0] for *_, terms in added if len(terms) == 1)

    picks = random.Random("eval A v2 added").sample(added, min(ADDED, len(added)))
    wanted = defaultdict(set)
    for year, article_id, _ in picks:
        wanted[year].add(article_id)
    v1_others = {
        y: c["articles"] - c["candidates"] for y, c in sorted(v1_counts.items())
    }
    rand, _, screen = random_picks(v1_others)
    screened = {y: rand[y] | screen[y] for y in years if rand[y] | screen[y]}
    with ProcessPoolExecutor(max_workers=6) as pool:
        items = [i for found in pool.map(year_items, wanted.items()) for i in found]
        caught = {}
        for found in pool.map(year_rescreen, screened.items()):
            caught |= found

    OUT.mkdir(parents=True, exist_ok=True)
    items = keep_judgments(
        OUT / "added.json",
        sorted(items, key=lambda i: (i["year"], i["article_id"])),
        lambda i: i["article_id"],
        ("first", "rejudged", "ghost_report", "note"),
    )
    judged = [i for i in items if i["ghost_report"] is not None]
    # "sample": the seeded tenth of negatives, judged blind; "full": read in full
    checked = [i for i in judged if i["rejudged"] == "sample"]
    full = [i for i in judged if i["rejudged"] == "full"]

    def totals(key):
        return {
            t: sum(c[key].get(t, 0) for c in v2_counts.values())
            for t in (*lexicon.GHOST, *lexicon.TOGETHER)
        }

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "checks": {
            "years": len(manifests),
            "code_versions": sorted({m["code_version"] for m in manifests}),
            "lexicon_versions": sorted({m["lexicon_version"] for m in manifests}),
            "v1_candidates": sizes["v1"],
            "v2_candidates": sizes["v2"],
            "v1_candidates_lost": len(missing),
            "added": len(added),
            "added_holding_an_old_term": len(old_terms),
        },
        "rules": {
            "new": new,
            "candidates": totals("by_term"),
            "only": totals("only_by_term"),
            "added_holding": {t: holding[t] for t in new},
            # what dropping the rule alone would take away
            "added_holding_only_it": {t: alone[t] for t in new},
        },
        "added": {
            "seed": "eval A v2 added",
            "sample": len(items),
            "judged": len(judged),
            "first_reading": dict(Counter(i["first"] for i in judged)),
            "negatives_rejudged": len(checked),
            "negatives_agreed": sum(not i["ghost_report"] for i in checked),
            "read_in_full": dict(
                Counter(
                    f"{i['first']} -> {'report' if i['ghost_report'] else 'no'}"
                    for i in full
                )
            ),
        },
    }
    articles = sum(v2_counts[y]["articles"] for y in years)
    non_candidates = articles - sizes["v2"]
    v1_reports = {
        r["article_id"]
        for path in ("screen.json", "recall.json")
        for r in json.loads((RESULTS / "eval_a" / path).read_text())
        if r.get("pool", "random") == "random" and r["ghost_report"]
    }
    drawn = sum(len(v) for v in screened.values())
    left = v1_reports - caught.keys()
    report["recall_in_sample"] = {
        "v1_screened": drawn,
        "v2_candidates_among_them": len(caught),
        "v1_reports": len(v1_reports),
        "caught": {a: caught[a] for a in sorted(v1_reports & caught.keys())},
        "missed": rate(len(left), drawn - len(caught), non_candidates),
    }
    if judged and len(judged) == len(items):
        found = sum(bool(i["ghost_report"]) for i in judged)
        report["added"] |= rate(found, len(judged), len(added))
        report["added"]["by_rule"] = summarise_rules(
            items,
            {t: holding[t] for t in new},
            {t: alone[t] for t in new},
            len(added),
        )
        report["added"]["reports"] = [
            {k: i[k] for k in ("article_id", "year", "date", "paper", "terms", "note")}
            for i in judged
            if i["ghost_report"]
        ]
        v1_eval = json.loads((RESULTS / "eval_a.json").read_text())
        report["recall_in_sample"]["recall"] = recall_in_sample(
            v1_eval["composition"]["categories"]["ghost_report"],
            report["added"],
            report["recall_in_sample"]["missed"],
        )
    (OUT / "lexicon_v2.json").write_text(json.dumps(report, indent=1) + "\n")
    c = report["checks"]
    print(
        f"{c['years']} years, code {c['code_versions']}; v1 {c['v1_candidates']:,} -> v2 "
        f"{c['v2_candidates']:,} candidates; {c['v1_candidates_lost']} lost, {c['added']:,} "
        f"added, {c['added_holding_an_old_term']} holding an old term"
    )
    print("added holding each rule:", report["rules"]["added_holding"])
    print(f"wrote {(OUT / 'lexicon_v2.json').relative_to(DATA.parent)}")


if __name__ == "__main__":
    main()
