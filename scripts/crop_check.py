"""The crop check (Phase 2A): 50 candidates at random with a fixed seed, one from each of 50
years spread across every year that has candidates, and no more than two from one LoC batch.
It caches each candidate's crops, one per box, and writes the picks to
eval/results/phase2a/crop-check.json and a contact sheet of the crops beside the first lines
of their OCR to data/crop-check/sheet.html.

Verdicts go into the JSON by hand after looking at the sheet. A second run keeps them, shows
them on the sheet, and writes eval/results/phase2a/crop-check.md once every pick has one.

    uv run python scripts/crop_check.py
"""

import html
import json
import random
from collections import Counter
from pathlib import Path

import httpx
import zstandard

from paperghosts.ingest.crops import batch, crop_urls, crops_for, page_service
from paperghosts.ingest.headline import display_headline

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "eval" / "results" / "phase2a"
PICKS_FILE = RESULTS / "crop-check.json"
SHEET = DATA / "crop-check" / "sheet.html"
SEED, PICKS, PER_BATCH = "crop check", 50, 2

STYLE = """
body { font: 13px/1.4 -apple-system, Helvetica, sans-serif; margin: 16px; color: #111;
  background: #fff; width: 1168px; }
.row { display: grid; grid-template-columns: 520px 1fr; gap: 20px;
  border-top: 1px solid #bbb; padding: 12px 0; }
.crops { max-height: 400px; overflow: hidden; }
.crops img { display: block; max-width: 520px; }
p { margin: 0 0 6px; }
.meta { color: #555; }
.headline { font-weight: 600; white-space: pre-line; }
.ocr { font: 12px/1.4 Menlo, monospace; white-space: pre-wrap; margin: 0 0 8px; }
.verdict { font-weight: 600; } .pass { color: #07743f; } .fail, .error { color: #b00020; }
"""


def spread(years, n):
    """n of the years, evenly spaced from the first to the last."""
    return [years[round(i * (len(years) - 1) / (n - 1))] for i in range(n)]


def pick(years, load, resolve, n=PICKS, per_batch=PER_BATCH):
    """A candidate from each of n years spread across them all, at random with a fixed
    seed, taking no more than per_batch from one LoC batch. resolve gives a candidate's
    IIIF service; a candidate whose service can't be found stays in, as a failure."""
    picks, taken = [], Counter()
    for year in spread(sorted(years), n):
        rows = [row for row in load(year) if row.get("bbox_list")]
        random.Random(f"{SEED} {year}").shuffle(rows)
        for row in rows:
            try:
                service = resolve(row)
            except LookupError as exc:
                picks.append(
                    {"year": year, "row": row, "service": None, "error": str(exc)}
                )
                break
            if taken[batch(service)] < per_batch:
                taken[batch(service)] += 1
                picks.append({"year": year, "row": row, "service": service})
                break
    return picks


def load(year):
    with zstandard.open(DATA / "candidates" / f"{year}.jsonl.zst", "rt") as rows:
        return [json.loads(row) for row in rows]


def entry(chosen, known):
    """A pick with its crops fetched (or read from the cache), and any verdict it has."""
    row, service = chosen["row"], chosen["service"]
    files, errors = [], [chosen["error"]] if "error" in chosen else []
    if service:
        try:
            service, paths = crops_for(
                row["member"], row["scan"], row["bbox_list"], service, row["text"]
            )
            files = [path.name for path in paths]
        except (httpx.HTTPError, LookupError, ValueError) as exc:
            errors.append(f"crops not fetched: {exc}")
    urls = crop_urls(service, row["bbox_list"]) if service else []
    text = [line.strip() for line in (row["text"] or "").splitlines() if line.strip()]
    return {
        "year": chosen["year"],
        "article_id": row["article_id"],
        "paper": row["paper"],
        "date": row["date"],
        "service": service,
        "batch": batch(service) if service else None,
        "boxes": len(row["bbox_list"]),
        "display_headline": display_headline(
            row["headline"], row["paper"], row["date"]
        ),
        "first_lines": text[:8],
        "crop_urls": urls,
        "crop_files": files,
        "errors": errors,
        "verdict": known.get("verdict"),
        "reason": known.get("reason"),
    }


def section(number, e):
    crops = (
        "".join(
            f'<img src="../crops/{name}" alt="box {box}">'
            if name
            else f'<p class="error">box {box} not fetched</p>'
            for box, name in enumerate(e["crop_files"], 1)
        )
        or '<p class="error">no crops</p>'
    )
    verdict = (e["verdict"] or "not yet checked").upper()
    if e["reason"]:
        verdict += f": {e['reason']}"
    meta = " · ".join(
        [
            f"{number}. {e['year']}",
            e["paper"] or "no title on record",
            e["date"] or "no date",
            f"batch {e['batch'] or '?'}",
            f"{e['boxes']} boxes",
        ]
    )
    return (
        f'<section class="row" id="c{number:02}"><div class="crops">{crops}</div><div>'
        f'<p class="meta">{html.escape(meta)}</p>'
        f'<p class="headline">{html.escape(e["display_headline"] or "(no headline)")}</p>'
        f'<pre class="ocr">{html.escape(chr(10).join(e["first_lines"]))}</pre>'
        f'<p class="verdict {e["verdict"] or ""}">{html.escape(verdict)}</p>'
        + "".join(f'<p class="error">{html.escape(x)}</p>' for x in e["errors"])
        + "</div></section>"
    )


def report(entries):
    passed = sum(e["verdict"] == "pass" for e in entries)
    lines = [
        "# Crop check",
        "",
        f"{passed} of {len(entries)} candidates pass ({100 * passed / len(entries):.0f}%).",
        "",
        "| # | Year | Paper | Date | Batch | Boxes | Verdict | Reason |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for number, e in enumerate(entries, 1):
        cells = [
            str(number),
            str(e["year"]),
            (e["paper"] or "no title on record").split(" [")[0].replace("|", "/"),
            e["date"] or "",
            e["batch"] or "?",
            str(e["boxes"]),
            e["verdict"],
            (e["reason"] or "").replace("|", "/"),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    (RESULTS / "crop-check.md").write_text("\n".join(lines) + "\n")


def main():
    counts = [json.loads(p.read_text()) for p in (DATA / "counts").glob("*.json")]
    years = [c["year"] for c in counts if c["candidates"]]
    known = {}
    if PICKS_FILE.exists():
        known = {e["article_id"]: e for e in json.loads(PICKS_FILE.read_text())}

    def resolve(
        row,
    ):  # a known pick keeps its service, so a second run asks loc.gov nothing
        if row["article_id"] in known and known[row["article_id"]]["service"]:
            return known[row["article_id"]]["service"]
        return page_service(row["member"], row["scan"])

    picks = pick(years, load, resolve)
    entries = [
        entry(chosen, known.get(chosen["row"]["article_id"], {})) for chosen in picks
    ]
    RESULTS.mkdir(parents=True, exist_ok=True)
    PICKS_FILE.write_text(json.dumps(entries, indent=1) + "\n")
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    SHEET.write_text(
        f'<!doctype html><meta charset="utf-8"><title>Crop check</title><style>{STYLE}</style>'
        + "".join(section(number, e) for number, e in enumerate(entries, 1))
    )
    taken = Counter(e["batch"] for e in entries if e["batch"])
    missing = sum(not e["crop_files"] for e in entries)
    print(
        f"{len(entries)} picks over {len(years)} years ({entries[0]['year']}-{entries[-1]['year']}), "
        f"{len(taken)} batches, at most {max(taken.values())} from one; "
        f"{sum(e['boxes'] for e in entries)} boxes, {missing} picks without crops, "
        f"{sum(not e['service'] for e in entries)} pages without a service"
    )
    if all(e["verdict"] for e in entries):
        report(entries)
        print(f"wrote {(RESULTS / 'crop-check.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
