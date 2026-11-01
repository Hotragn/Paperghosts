"""Every number the write-up quotes, each read at run time from a committed results file or doc and
printed with its source: the file and its JSON key path, or the doc and its line. Only the gemma4
thinking-on timing is written in by hand, since its one record is Ollama's server log. The test count
comes from pytest's collection. Reads files only: no model, network or Ollama call. It isn't named
numbers.py, since in scripts/ that would shadow the standard library's numbers, which numpy imports.

  uv run python scripts/article_numbers.py
Writes eval/results/numbers.json.
"""

import json
import re
import subprocess
from collections import Counter

from label_gold import OUT, ROOT, saved

RESULT = ROOT / "eval" / "results" / "numbers.json"
P2C = "eval/results/phase2c"


def at(rel: str, path: str = "", *fields) -> tuple:
    found = json.loads((ROOT / rel).read_text())
    for key in path.split(".") if path else []:
        found = found[key]
    if fields:
        found = {f: found[f] for f in fields}
    keys = f" {{{', '.join(fields)}}}" if fields else ""
    return found, f"{rel}: {path or '(top)'}{keys}"


def number(text: str):
    if re.fullmatch(r"\d[\d,_]*", text):
        return int(text.replace(",", "").replace("_", ""))
    return float(text) if re.fullmatch(r"\d+\.\d+", text) else text


def doc(rel: str, pattern: str) -> tuple:
    for i, line in enumerate((ROOT / rel).read_text().splitlines(), 1):
        if m := re.search(pattern, line):
            got = [number(g) for g in m.groups()]
            return (got[0] if len(got) == 1 else got), f"{rel}:{i}"
    raise ValueError(f"{pattern!r} is not in {rel}")


def row(name: str, got: tuple, note: str = "") -> dict:
    return {"name": name, "value": got[0], "source": got[1]} | (
        {"note": note} if note else {}
    )


def spend() -> list:
    """The rows of BUDGET.md's table of today's Tinker use, under its spend-stopped heading."""
    rel, found, inside = "Docs/BUDGET.md", [], False
    for i, line in enumerate((ROOT / rel).read_text().splitlines(), 1):
        inside = line.startswith("## Spend stopped") or (
            inside and not line.startswith("## ")
        )
        cells = [c.strip(" *") for c in line.strip().strip("|").split("|")]
        if inside and len(cells) == 4 and cells[1].replace(",", "").isdigit():
            value = {
                "prompt_tokens": number(cells[1]),
                "generated_tokens": number(cells[2]),
                "cost_all_cached_to_none": cells[3],
            }
            found.append(
                {
                    "name": f"tinker spend: {cells[0]}",
                    "value": value,
                    "source": f"{rel}:{i}",
                }
            )
    return found


def kinds(split: str) -> tuple:
    path = OUT[split]
    counted = Counter(r["kind"] for r in saved(path))
    return dict(counted.most_common()), f"{path.relative_to(ROOT)}: count of each kind"


def teacher(round_name: str, label: str) -> list:
    rel = f"{P2C}/teacher_dev_{round_name}.json"
    scored = json.loads((ROOT / rel).read_text())
    found = [
        row(f"{label}: model", at(rel, "model")),
        row(f"{label}: thinking", at(rel, "thinking")),
        row(f"{label}: report recall", at(rel, "report_recall")),
        row(
            f"{label}: kind, after the verifier",
            at(rel, "accuracy_verified.kind", "agree", "n", "interval", "kappa"),
        ),
        row(
            f"{label}: report or not, after the verifier",
            at(rel, "accuracy_verified.report", "agree", "n", "interval", "kappa"),
        ),
    ]
    for name in scored["accuracy_verified"]["fields"]:
        got = at(rel, f"accuracy_verified.fields.{name}", "agree", "n", "interval")
        found.append(row(f"{label}: {name}, after the verifier", got))
    return found


def formats() -> list:
    rel, found = f"{P2C}/format_check.json", []
    for round_name in ("g26", "r3"):
        for name in ("outcome", "place_state", "place_type", "precision"):
            path = f"{round_name}.{name}"
            found += [
                row(
                    f"format check {round_name}: {name}, strict",
                    at(rel, path, "agree", "n", "interval"),
                ),
                row(
                    f"format check {round_name}: {name}, normalised (scoring only)",
                    at(rel, path, "normalised_agree", "n", "normalised_interval"),
                    "normalisation is for scoring only; training labels go through teacher.verified",
                ),
            ]
    return found


def entries() -> list:
    v1, v2, lex = (
        "eval/results/eval_a.json",
        "eval/results/eval_a_v2.json",
        "eval/results/eval_a_v2/lexicon_v2.json",
    )
    clusters, decisions, budget = (
        "eval/results/phase2b/clusters.json",
        "Docs/DECISIONS.md",
        "Docs/BUDGET.md",
    )
    gold_draw, through = f"{P2C}/gold_draw.json", f"{P2C}/local_throughput.json"
    strata = at(gold_draw, "expected_reports.strata")
    return [
        # the corpus and the candidates
        row("archive: pages and articles", at(v2, "totals", "pages", "articles")),
        row(
            "candidates, lexicon v2 (the reader's full pass)",
            at(v2, "totals.candidates"),
            "every lexicon v2 candidate in the archive",
        ),
        row(
            "CANDIDATES constant",
            doc("scripts/local_teacher.py", r"^CANDIDATES = ([\d_]+)"),
        ),
        row("near-miss articles, lexicon v2", at(v2, "totals.near_miss")),
        row(
            "training pool, articles",
            at(f"{P2C}/leakage.json", "pool"),
            "every candidate and near-miss reservoir article outside the 6,567 held out",
        ),
        row("held out of the pool", at(f"{P2C}/leakage.json", "out_of_pool")),
        row(
            "credit check: sample, and candidates in the pool",
            doc(budget, r"a seeded (\d+) of the ([\d,]+) candidates in the pool"),
            "the pool's articles that are candidates (credit_check.py pool); not reconciled with 1,236,122",
        ),
        # lexicon v1 against v2, and eval A
        row(
            "lexicon v1 against v2",
            at(
                lex,
                "checks",
                "v1_candidates",
                "v2_candidates",
                "v1_candidates_lost",
                "added",
            ),
        ),
        row(
            "lexicon v2: added and its share",
            doc(decisions, r"rules add ([\d,]+) candidates \(\+([\d.]+)%\)"),
        ),
        row("candidates per million, v1", at(v1, "totals.candidates_per_million")),
        row("candidates per million, v2", at(v2, "totals.candidates_per_million")),
        row(
            "lexicon v2's added: reports in the judged 200",
            at(
                lex,
                "added",
                "count",
                "n",
                "share",
                "low",
                "high",
                "implied",
                "implied_low",
                "implied_high",
            ),
        ),
        row("lexicon v2 recall, in-sample", at(lex, "recall_in_sample.recall.point")),
        row(
            "lexicon v1 recall, from the flag-word screen",
            at(v1, "recall.screen.recall"),
        ),
        row(
            "eval A: ghost reports among candidates",
            at(
                v1,
                "composition.categories.ghost_report",
                "count",
                "n",
                "share",
                "low",
                "high",
                "implied",
                "implied_low",
                "implied_high",
            ),
        ),
        row(
            "eval A: reports in the near-miss sample",
            at(v1, "recall.near_miss", "count", "n", "high", "implied_high"),
        ),
        row(
            "eval A: reports in the random sample",
            at(v1, "recall.random", "count", "n", "high", "implied_high"),
        ),
        row(
            "eval A: flag-word screen of non-candidates",
            at(
                v1,
                "recall.screen.random",
                "count",
                "n",
                "share",
                "low",
                "high",
                "implied",
            ),
        ),
        row(
            "eval A reprints, v1",
            at(v1, "reprints", "clusters", "share_clustered", "distinct_stories"),
        ),
        row(
            "eval A reprints, v2",
            at(v2, "reprints", "clusters", "share_clustered", "distinct_stories"),
        ),
        # stories and reprints (decision 36), and the reservoir
        row("stories: threshold", at(clusters, "threshold")),
        row(
            "stories: precision per candidate",
            at(clusters, "evaluation.per candidate.precision"),
        ),
        row(
            "stories: recall per candidate",
            at(clusters, "evaluation.per candidate.recall"),
        ),
        row(
            "stories: chained large clusters, and eval A's precision per candidate (%)",
            doc(
                decisions,
                r"in (\d+) of the (\d+) largest clusters.*against eval A's ([\d.]+)%",
            ),
        ),
        row(
            "stories: distinct, v2",
            at(
                clusters,
                "stories",
                "distinct_stories",
                "with_more_than_one_printing",
                "printings_in_them",
                "cross_paper",
            ),
        ),
        row(
            "stories: eval A's distinct stories on v2",
            at(clusters, "frame.distinct_stories"),
        ),
        row(
            "stories: the reader's job by stories",
            at(
                clusters,
                "reader",
                "first_printings",
                "loose_members_read_too",
                "job",
                "of_candidates",
            ),
        ),
        row(
            "reservoir: sample per pool per year",
            doc(decisions, r"keeps a ([\d,]+)-article sample of each pool per year"),
        ),
        row(
            "reservoir: near-miss reservoir articles",
            doc(decisions, r"and the ([\d,]+) articles of the near-miss reservoir"),
        ),
        row("grouping: articles, groups, largest", at(gold_draw, "grouping")),
        # gold and dev
        row("gold and dev articles", at(gold_draw, "split", "gold", "dev")),
        row("strata", (len(strata[0]), strata[1] + " (count of keys)")),
        row(
            "expected gold reports, with its range",
            at(gold_draw, "expected_reports.total"),
        ),
        row("gold kinds", kinds("gold")),
        row("dev kinds", kinds("dev")),
        row(
            "weighted report rate",
            at(f"{P2C}/gold_measures.json", "weighted_report_rate"),
        ),
        row(
            "story-place rule",
            at(
                f"{P2C}/gold_measures.json",
                "story_place_rule",
                "places",
                "agree",
                "rate",
                "interval",
                "cases",
            ),
        ),
        row(
            "paper's state against labelled states",
            at(f"{P2C}/gold_measures.json", "story_place_rule.paper_state"),
        ),
        # first pass against second pass, and the blind re-ruling
        row(
            "first vs second pass on gold: kind",
            at(
                f"{P2C}/agreement.json",
                "gold.kind",
                "agree",
                "n",
                "interval",
                "kappa",
                "kappa_interval",
            ),
        ),
        row(
            "first vs second pass on gold: report or not",
            at(
                f"{P2C}/agreement.json",
                "gold.report",
                "agree",
                "n",
                "interval",
                "kappa",
                "kappa_interval",
            ),
        ),
        row(
            "blind re-ruling: kind, same as the first rulings",
            at(f"{P2C}/blind_rulings.json", "kind"),
        ),
        row(
            "blind re-ruling: rulings that differed, blind taken, first kept",
            doc(
                decisions,
                r"(\d+) articles' blind rulings differ.*took the blind ruling in (\d+) and kept mine in (\d+)",
            ),
        ),
        # the teachers on dev
        *teacher("r3", "Qwen3.5-397B round 3"),
        *teacher("g26", "gemma4:26b thinking off"),
        *formats(),
        # the Tinker spend
        row(
            "tinker: balance and unpaid usage ($)",
            doc(
                budget,
                r"remaining credit balance of \$([\d.]+), with \$([\d.]+) of unpaid usage",
            ),
        ),
        *spend(),
        row(
            "tinker: thinking round, unrecorded at most ($)",
            doc(budget, r"or \$([\d.]+) more at the uncached rate"),
        ),
        row(
            "credit check: teacher billed",
            at(f"{P2C}/credit_check.json", "teacher.billed"),
            "empty: billing hadn't caught up",
        ),
        row(
            "credit check: student billed",
            at(f"{P2C}/credit_check.json", "student.billed"),
            "empty: billing hadn't caught up",
        ),
        # local throughput
        row("local qwen3.5:4b model", at(through, "model")),
        *[
            row(
                f"local qwen3.5:4b, long prompt, {r['concurrent']} at once",
                (r, f"{through}: runs[{i}]"),
            )
            for i, r in enumerate(at(through, "runs")[0])
        ],
        row(
            "local qwen3.5:4b, short prompt",
            at(
                through,
                "short",
                "concurrent",
                "articles_per_hour",
                "prompt_tokens",
                "full_pass_days",
            ),
        ),
        row("local qwen3.5:4b, prefix", at(through, "prefix")),
        row(
            "gemma4 thinking off, local",
            at(
                f"{P2C}/local_teacher.json",
                "g26",
                "articles_per_hour",
                "draw_of_3000_hours",
                "wall_seconds",
                "articles",
            ),
        ),
        # shortcut: gemma4 thinking on has no results file, only Ollama's log; read a file once a run is saved
        {
            "name": "gemma4 thinking on, local",
            "value": {"articles": 6, "minutes_each": [2.4, 8.1]},
            "source": "Ollama server log, 2026-10-31 17:00–17:30 (not committed)",
            "note": "hard-coded: no results file",
        },
        *submission(),
    ]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, cwd=ROOT, capture_output=True, text=True
    ).stdout


def per_ten_thousand(prompt: int, generated: int, articles: int, rates: list) -> list:
    """Round 3's measured tokens per article, priced per 10,000 articles, all cached to none."""
    cached, uncached, out = rates
    return [
        round((prompt * rate + generated * out) / 1e6 / articles * 10_000, 2)
        for rate in (cached, uncached)
    ]


def sentry() -> list:
    """Sentry's p50 and p95 per Atlas query kind, for each release pulled (decision 40)."""
    rel = "eval/results/sentry_latency.json"
    found = json.loads((ROOT / rel).read_text())
    return [
        row(
            "Sentry: the Morgue's page loads by span op (ms), scripted loads, not visitors"
            if key == "web"
            else f"Sentry: Atlas query latency (ms), release {key[:7]}",
            (
                {
                    q["query"]: [q["p50_ms"], q["p95_ms"], q["count"]]
                    for q in v["spans"]
                },
                f"{rel}: {key}.spans, as [p50, p95, count]",
            ),
        )
        for key, v in found.items()
    ]


def submission() -> list:
    """The submission's figures: the 1850 probe, the Morgue, Atlas, Tinker's price per 10,000
    articles, Entire's checkpoints and decision 39's disclosure."""
    env, demo, r3 = (
        "eval/results/phase1_env.json",
        "web/public/reports.json",
        f"{P2C}/teacher_dev_r3.json",
    )
    reports = json.loads((ROOT / demo).read_text())
    tokens = at(r3, "", "prompt_tokens", "output_tokens", "articles")[0]
    rates = doc(
        "Docs/BUDGET.md",
        r"Qwen3\.5-397B-A17B, the teacher \| \$([\d.]+), \$([\d.]+) \| \$([\d.]+)",
    )
    trailers = git(
        "log", "--all", "--format=%(trailers:key=Entire-Checkpoint,valueonly)"
    ).split()
    refs = git("for-each-ref", "--format=%(refname)", "refs/entire/checkpoints").split()
    archive = at("eval/results/eval_a_v2.json", "totals.candidates")[0]
    in_pool = doc(
        "Docs/BUDGET.md", r"a seeded \d+ of the ([\d,]+) candidates in the pool"
    )[0]
    held_out = at(f"{P2C}/leakage.json", "out_of_pool")[0]
    return [
        row("1850 probe: articles in 1850's file", at(env, "faro_1850.articles")),
        row(
            "1850 probe: the Stratford knockings",
            at(
                env,
                "faro_1850.stratford_knockings",
                "matching_articles",
                "naming_phelps",
                "first",
            ),
        ),
        row(
            "the Morgue: reports, clippings, with the paper's place, with a story state",
            (
                [
                    len(reports),
                    sum(len(r["clippings"]) for r in reports),
                    sum(bool(r["printed_in"]["place"]) for r in reports),
                    sum(bool(r["place_state"]) for r in reports),
                ],
                f"{demo}: counted",
            ),
        ),
        row(
            "Atlas: the Morgue's reports loaded",
            at(
                "eval/results/atlas_demo.json",
                "",
                "documents",
                "storage_kb",
                "load_seconds",
                "with_location",
            ),
        ),
        row(
            "Tinker: the 397B teacher's price per 10,000 articles, all cached to none ($)",
            (
                per_ten_thousand(
                    tokens["prompt_tokens"],
                    tokens["output_tokens"],
                    tokens["articles"],
                    rates[0],
                ),
                f"{r3}: prompt_tokens, output_tokens, articles; rates {rates[1]}",
            ),
        ),
        row(
            "Entire: commits with an Entire-Checkpoint trailer, and checkpoint refs",
            (
                [len(trailers), len(refs)],
                "git log --all trailers; git for-each-ref refs/entire/checkpoints",
            ),
        ),
        row(
            "candidates: in the archive but not in the training pool, and the articles held out",
            (
                [archive - in_pool, held_out],
                (
                    "eval/results/eval_a_v2.json: totals.candidates, less Docs/BUDGET.md's "
                    f"candidates in the pool; {P2C}/leakage.json: out_of_pool"
                ),
            ),
            "the difference fits the articles held out as gold, dev and their reprints, but it was "
            "not checked article by article",
        ),
        *sentry(),
        row(
            "Atlas: the papers' towns geocoded and loaded",
            at(
                "eval/results/atlas_places.json",
                "",
                "printed_in_towns",
                "geocoded",
                "reports_covered",
                "storage_kb",
            ),
        ),
        {
            "name": "Atlas Vector Search: not built",
            "value": "first the Hugging Face token lacked the Inference Providers permission (HTTP 403), then with it the account had no credits left (HTTP 402), and buying credits is spending the owner ruled out; ghosts like this one uses Atlas Search's moreLikeThis",
            "source": "Hugging Face router, feature-extraction for all-MiniLM-L6-v2 and bge-small-en-v1.5, HTTP 403 then 402, 2026-10-31 (not committed)",
            "note": "hard-coded: a refusal leaves no results file",
        },
        row(
            "decision 39: the disclosure",
            doc(
                "Docs/DECISIONS.md",
                r"^\*\*39\. (No Tinker spend at all, and step 2C runs on this Mac)",
            ),
            "the reader is untrained; the Morgue shows labelled reports, not the reader's output",
        ),
    ]


def main() -> None:
    found = entries()
    lines = subprocess.run(
        ["uv", "run", "pytest", "--collect-only", "-q"],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    last = lines.splitlines()[-1]
    found.append(
        {
            "name": "tests collected",
            "value": int(last.split()[0]),
            "source": f"uv run pytest --collect-only -q, last line: {last!r}",
        }
    )
    RESULT.write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n")
    # the Morgue's "How we know" page reads the same sheet
    (ROOT / "web" / "public" / "numbers.json").write_text(RESULT.read_text())
    for e in found:
        note = f"  ({e['note']})" if "note" in e else ""
        print(
            f"{e['name']}: {json.dumps(e['value'], ensure_ascii=False)}  [{e['source']}]{note}"
        )


if __name__ == "__main__":
    main()
