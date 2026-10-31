"""The Morgue's data: web/public/reports.json, from the frozen gold and dev labels whose kind is
report. Each entry has the article's paper, date, headline and OCR text, the label's fields with
their quotes, each quote checked by the teacher's verifier and placed in the text, and its
clippings, copied from the crop cache into web/public/crops with their tile.loc.gov URLs and the
issue's loc.gov page. Nothing is fetched: crops.get is replaced by one that refuses, so a page the
cache doesn't hold keeps its cached crop files but no URLs.

  uv run python scripts/export_demo.py
"""

import html
import json
import re
import shutil
from pathlib import Path

from label_gold import OUT, ROOT, SEEN, articles, saved, squeezed
from teacher import verified

from paperghosts.geo.loc import recorded, title_record
from paperghosts.ingest import crops

WEB = ROOT / "web" / "public"
FIELDS = (
    "place",
    "place_state",
    "seen",
    "outcome",
    "specific_place",
    "place_type",
    "precision",
)
THRESHOLD = 0.70  # the verifier's threshold, calibrated on dev (RDR-9)
# shortcut: macOS's word list scores OCR legibility; swap in a period word list if one is adopted
WORDLIST = Path("/usr/share/dict/words")
WORDS = (
    {w.lower() for w in WORDLIST.read_text().split()} if WORDLIST.exists() else set()
)


def refuse(url, **params):
    raise RuntimeError(f"export_demo fetches nothing: {url}")


def span(quote: str, text: str) -> list | None:
    """Where a quote sits in the text, its words matched across any spacing, or None."""
    words = quote.split()
    if not words:
        return None
    pattern = r"\s+".join(map(re.escape, words))
    found = re.search(pattern, text) or re.search(pattern, text, re.IGNORECASE)
    return [found.start(), found.end()] if found else None


def legible(text: str) -> float:
    """The share of a text's words of three letters or more that are dictionary words: how much
    of its OCR reads as English, for ordering the demo and titling garbled headlines."""
    found = re.findall(r"[A-Za-z]{3,}", text)
    return (
        round(sum(w.lower() in WORDS for w in found) / len(found), 3) if found else 0.0
    )


def printed_in(row: dict) -> dict:
    """Where the paper was printed: its cached loc.gov title record, else the place its LoC title
    gives in brackets ("(Boston [Mass.])") with the row's state. The paper's place, never the
    story's; the LCCN alone when neither names one."""
    lccn = row.get("lccn") or ""
    try:
        found = recorded(title_record(lccn)) or {}
    except RuntimeError:
        found = {}
    if found.get("place"):
        return {
            "lccn": lccn,
            "place": found["place"],
            "state": found.get("state"),
            "from": "title record",
        }
    titled = re.search(
        r"\(([^()]*)\)\s*\d{3}[\d?]", html.unescape(row.get("paper") or "")
    )
    place = re.sub(r"\s*\[.*?\]|,.*$", "", titled[1]).strip() if titled else None
    return {
        "lccn": lccn,
        "place": place or None,
        "state": row.get("state"),
        "from": "paper title",
    }


def issue_page(service: str) -> str:
    lccn, _, issue, _ = crops.place(service)
    return f"https://www.loc.gov/item/{lccn}/{issue[:4]}-{issue[4:6]}-{issue[6:8]}/ed-{int(issue[8:])}/"


def clippings(row: dict, cached: list) -> tuple[list, str | None]:
    """The article's crops as web paths with their tile.loc.gov URLs, and its issue's page."""
    urls, page = [None] * len(cached), None
    try:
        service, _ = crops.crops_for(
            row["member"], row["scan"], row["bbox_list"], text=row.get("text")
        )
        urls, page = crops.crop_urls(service, row["bbox_list"]), issue_page(service)
    except (RuntimeError, LookupError, ValueError):
        pass  # the cache doesn't name this page's service, so the clipping shows without a link
    out = []
    for path, url in zip(cached, urls, strict=False):
        source = Path(path)
        target = WEB / "crops" / source.name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        out.append({"src": f"crops/{source.name}", "loc": url})
    return out, page


def entry(label: dict, row: dict, cached: list) -> dict:
    headline, text = row.get("headline") or "", row.get("text") or ""
    kept = verified(label, squeezed(f"{headline}\n{text}"), THRESHOLD)[0]

    def field(stated, held):
        if not stated:
            return None
        return {
            "value": stated["value"],
            "quote": stated["quote"],
            "verified": bool(held),
            "in_text": span(stated["quote"], text),
            "in_headline": span(stated["quote"], headline),
        }

    clips, page = clippings(row, cached)
    return {
        "article_id": label["article_id"],
        "paper": row.get("paper"),
        "date": row.get("date"),
        "headline": headline,
        "text": text,
        **{name: field(label.get(name), kept.get(name)) for name in FIELDS},
        "people": [field(p, p in kept["people"]) for p in label.get("people") or []],
        "printed_in": printed_in(row),
        "headline_legible": legible(headline),
        "text_legible": legible(text),
        "clippings": clips,
        "issue_page": page,
    }


def main() -> None:
    crops.get = refuse
    reports = [
        r
        for split in ("gold", "dev")
        for r in saved(OUT[split])
        if r["kind"] == "report"
    ]
    rows = articles()
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {}
    found = [
        entry(
            r, rows[r["article_id"]], seen.get(r["article_id"], {}).get("crops") or []
        )
        for r in sorted(reports, key=lambda r: rows[r["article_id"]].get("date") or "")
    ]
    # legible reports lead, in tenths of their text's legibility, then by date
    found.sort(key=lambda e: (-round(e["text_legible"], 1), e["date"] or ""))
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "reports.json").write_text(json.dumps(found, indent=1) + "\n")
    print(
        f"{len(found)} reports, {sum(bool(e['clippings']) for e in found)} with clippings, "
        f"{sum(bool(e['issue_page']) for e in found)} with a loc.gov page, "
        f"{sum(bool(e['printed_in']['place']) for e in found)} with the paper's place"
    )


if __name__ == "__main__":
    main()
