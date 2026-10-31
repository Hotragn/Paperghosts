"""The gold labelling page (decision 37), served on 127.0.0.1 only.

Each gold and dev article's OCR text sits beside its crops. The crops come through crops_for,
so a page whose member and batch path disagree is checked before its crop is shown.
POLICY.md's rules are at hand, and each of RDR-2's fields takes its quote from a selection in
the text. A label is saved only if every quote is in the text. Each labeller gets one label
per article, saved to eval/gold/labels.jsonl or dev_labels.jsonl. Articles come in a seeded
shuffle, with no stratum or weight shown.

  serve [labeller]          the page; then open http://127.0.0.1:8765
  crops                     every article's crops through crops_for, one article at a time,
                            into the cache, listed in data/gold/crops.json
  show SPLIT N [labeller]   the split's next N articles the labeller hasn't labelled, as text
  check FILE                every label in a JSON-lines file through checked(), saving none
  save FILE [labeller]      the same, saving each label that passes
"""

import json
import random
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from functools import partial
from html import escape
from pathlib import Path
from typing import get_args

import httpx
import uvicorn
import zstandard
from check_leakage import SPLIT, paths_of
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from paperghosts.ingest import crops
from paperghosts.schemas import Outcome, PlaceType, Precision

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "gold"
POLICY = GOLD / "POLICY.md"
OUT = {"gold": GOLD / "labels.jsonl", "dev": GOLD / "dev_labels.jsonl"}
SEEN = (
    ROOT / "data" / "gold" / "crops.json"
)  # each article's crop files, or why it has none
KINDS = ("report", "fiction", "idiom", "religious", "advert", "other")
# the schema's values, which POLICY.md writes with spaces: inn_or_hotel is "inn or hotel"
CHOICES = {
    "outcome": get_args(Outcome),
    "place_type": get_args(PlaceType),
    "precision": get_args(Precision),
}
FIELDS = (
    "place",
    "place_state",
    "seen",
    "outcome",
    "specific_place",
    "place_type",
    "precision",
)
RULE = re.compile(r"^(\d+)\. \*\*(.+?)\*\*", re.MULTILINE)
# the edge-case slices a label records (SRS 7.3), as POLICY.md's label record lists them
SLICES = dict(re.findall(r"^  - (E\d+): (.+)$", POLICY.read_text(), re.MULTILINE))
CROP = re.compile(r"[0-9a-f]{24}\.jpg")


def rows_in(path: Path, wanted: set) -> list:
    with zstandard.open(path, "rt") as rows:
        return [row for row in map(json.loads, rows) if row["article_id"] in wanted]


def articles(root: Path = ROOT) -> dict:
    """Each gold and dev article's row, from the candidates or the near-miss reservoir, with
    the split it belongs to."""
    split = json.loads(SPLIT.read_text())
    wanted = {item["article_id"]: name for name in OUT for item in split[name]}
    with ProcessPoolExecutor(max_workers=8) as pool:
        parts = pool.map(partial(rows_in, wanted=set(wanted)), paths_of(root))
        return {
            row["article_id"]: dict(row, split=wanted[row["article_id"]])
            for part in parts
            for row in part
        }


def order_of(rows: dict) -> list:
    """Gold, then dev, each in its seeded shuffle."""
    order = []
    for name in OUT:
        ids = sorted(aid for aid, row in rows.items() if row["split"] == name)
        random.Random(f"2C.1 labelling order {name}").shuffle(ids)
        order += ids
    return order


def warm(rows: dict, crops_for=crops.crops_for, seen: Path = SEEN) -> dict:
    """Each article's crops through crops_for, one article at a time, as crops.get paces the
    Library of Congress: its crop files, or why it has none. Saved after each article, so a
    stop loses nothing. A busy answer is left out, so the next run asks again."""
    found = json.loads(seen.read_text()) if seen.exists() else {}
    for aid in order_of(rows):
        row = rows[aid]
        if aid in found:
            continue
        try:
            if not (row.get("scan") and row.get("bbox_list")):
                raise LookupError("the article has no scan or no boxes")
            _, paths = crops_for(
                row["member"], row["scan"], row["bbox_list"], text=row.get("text")
            )
            found[aid] = {"crops": [str(path) for path in paths]}
        except crops.Busy:
            continue
        except (LookupError, ValueError, httpx.HTTPError) as error:
            found[aid] = {"none": str(error)}
        seen.parent.mkdir(parents=True, exist_ok=True)
        seen.write_text(json.dumps(found, indent=1) + "\n")
    return found


def show(rows: dict, labeller: str, split: str, count: int, out=OUT, seen=SEEN) -> str:
    """The split's next `count` articles this labeller hasn't labelled, in the labelling
    order, as text to read: no stratum and no weight."""
    done = {r["article_id"] for r in saved(out[split]) if r["labeller"] == labeller}
    cropped = json.loads(seen.read_text()) if seen.exists() else {}
    picked = [a for a in order_of(rows) if rows[a]["split"] == split and a not in done]
    return "\n\n".join(shown(aid, rows[aid], cropped) for aid in picked[:count])


def shown(aid: str, row: dict, cropped: dict) -> str:
    """One article as text to read: its paper, date, crops, headline and OCR text."""
    crop = cropped.get(aid, {})
    return (
        f"=== {aid}\n{row.get('paper')} · {row.get('date')}\n"
        f"crops: {crop.get('crops') or crop.get('none')}\n"
        f"headline: {row.get('headline') or ''}\n---\n{row.get('text') or ''}"
    )


def save_file(
    path: Path, rows: dict, labeller: str, out=OUT, dry: bool = False
) -> list:
    """Each label in a JSON-lines file, through checked(), saved unless dry. Returns what's
    wrong with the others, article by article."""
    errors = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        label = json.loads(line)
        row = rows.get(label.get("article_id"))
        if row is None:
            errors.append(f"{label.get('article_id')}: not a gold or dev article")
            continue
        try:
            record = checked(label, row, labeller)
        except ValueError as error:
            errors.append(f"{row['article_id']}: {error}")
            continue
        if not dry:
            save(out[row["split"]], record)
    return errors


def squeezed(text: str) -> str:
    return " ".join(text.split())


def checked(label: dict, row: dict, labeller: str) -> dict:
    """The label as it's saved. A ValueError names what's wrong: a kind POLICY.md doesn't have,
    fields on an article that isn't a report, a value without its quote, a choice the schema
    doesn't have, or a quote that isn't in the text."""
    text = squeezed(f"{row.get('headline') or ''}\n{row.get('text') or ''}")

    def quoted(name: str, stated) -> dict | None:
        if not stated:
            return None
        value, quote = (stated.get("value") or "").strip(), (stated.get("quote") or "")
        if not value or not quote.strip():
            raise ValueError(f"{name}: a value needs its quote, and a quote its value")
        if name in CHOICES and value not in CHOICES[name]:
            raise ValueError(
                f"{name}: {value!r} is not one of {', '.join(CHOICES[name])}"
            )
        if squeezed(quote) not in text:
            raise ValueError(f"{name}: the quote isn't in the text: {quote!r}")
        return {"value": value, "quote": quote.strip()}

    kind = label.get("kind")
    if kind not in KINDS:
        raise ValueError(f"kind: choose one of {', '.join(KINDS)}")
    if not (label.get("kind_quote") or "").strip():
        raise ValueError("kind: quote the span that shows it")
    if squeezed(label["kind_quote"]) not in text:
        raise ValueError(f"kind: the quote isn't in the text: {label['kind_quote']!r}")
    fields = {name: quoted(name, label.get(name)) for name in FIELDS}
    slices = label.get("slices") or []
    unknown = [name for name in slices if name not in SLICES]
    if unknown:
        raise ValueError(f"slices: {', '.join(unknown)} isn't one of POLICY.md's")
    people = [quoted("people", person) for person in label.get("people") or []]
    if kind != "report" and (any(fields.values()) or people):
        raise ValueError("fields are for reports only")
    return {
        "article_id": row["article_id"],
        "kind": kind,
        "kind_quote": label["kind_quote"].strip(),
        **fields,
        "people": people,
        "rules": sorted({int(rule) for rule in label.get("rules") or []}),
        "slices": sorted(set(slices), key=list(SLICES).index),
        "crop_used": bool(label.get("crop_used")),
        "note": (label.get("note") or "").strip(),
        "labeller": labeller,
        "labelled_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def saved(path: Path) -> list:
    return (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )


def save(path: Path, record: dict) -> None:
    """One label per article and labeller: a new one replaces the old."""
    kept = [
        r
        for r in saved(path)
        if (r["article_id"], r["labeller"])
        != (record["article_id"], record["labeller"])
    ]
    partial_path = path.with_name(f"{path.name}.partial")
    partial_path.write_text("".join(json.dumps(r) + "\n" for r in [*kept, record]))
    partial_path.replace(path)


def box(name: str, stated: dict | None, choices=None, kind: str = "field") -> str:
    """One field, or one person: its value, as text or a choice, and its quote, taken from a
    selection."""
    stated = stated or {}
    value = escape(stated.get("value") or "", quote=True)
    if choices:
        options = "".join(
            f'<option value="{c}"{" selected" if c == stated.get("value") else ""}>'
            f"{c.replace('_', ' ')}</option>"
            for c in choices
        )
        entry = f'<select class="value"><option value=""></option>{options}</select>'
    else:
        entry = f'<input class="value" value="{value}">'
    quote = escape(stated.get("quote") or "", quote=True)
    return (
        f'<div class="{kind}" data-name="{name}"><b>{name.replace("_", " ")}</b> {entry}'
        f'<input class="quote" placeholder="quote" value="{quote}">'
        '<button type="button" class="take">⇐ selection</button></div>'
    )


SCRIPT = """
document.addEventListener("mousedown", e => {
  if (e.target.classList.contains("take")) e.preventDefault();  // keep the text selected
});
document.addEventListener("click", e => {
  if (e.target.classList.contains("take"))
    e.target.previousElementSibling.value = window.getSelection().toString().trim();
});
document.getElementById("add").onclick = () => {
  const row = document.querySelector(".person").cloneNode(true);
  row.querySelectorAll("input").forEach(input => input.value = "");
  document.getElementById("people").append(row);
};
const stated = el => {
  const value = el.querySelector(".value").value.trim();
  const quote = el.querySelector(".quote").value.trim();
  return value || quote ? {value, quote} : null;
};
document.getElementById("save").onclick = async () => {
  const form = document.getElementById("form");
  const label = {
    article_id: form.dataset.id,
    kind: (form.querySelector("[name=kind]:checked") || {}).value || null,
    kind_quote: form.querySelector("[name=kind_quote]").value,
    people: [...form.querySelectorAll(".person")].map(stated).filter(Boolean),
    rules: [...form.querySelectorAll("[name=rule]:checked")].map(b => +b.value),
    slices: [...form.querySelectorAll("[name=slice]:checked")].map(b => b.value),
    crop_used: form.querySelector("[name=crop_used]").checked,
    note: form.querySelector("[name=note]").value,
  };
  form.querySelectorAll(".field").forEach(el => label[el.dataset.name] = stated(el));
  const response = await fetch("/label", {
    method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(label),
  });
  const result = await response.json();
  const shown = document.getElementById("result");
  shown.textContent = response.ok ? "Saved. " : JSON.stringify(result.detail);
  if (response.ok && result.next) shown.innerHTML += `<a href="${result.next}">Next</a>`;
};
"""
STYLE = """
body{margin:0;font:14px/1.45 system-ui,sans-serif;color:#1b1b1b;background:#fbfbf9}
main{display:grid;grid-template-columns:1fr 1fr 460px;height:100vh}
main>section{overflow:auto;padding:12px;border-right:1px solid #ddd}
#text{white-space:pre-wrap;font:15px/1.5 Georgia,serif}
img{max-width:100%;display:block;margin-bottom:8px;border:1px solid #ccc}
.field,.person{margin:6px 0}.value{width:45%}.quote{width:38%}
pre{white-space:pre-wrap;font-size:12px}.error{color:#a00}
"""


def app(
    rows: dict, labeller: str, crops_for=crops.crops_for, out=OUT, crop_dir=crops.CROPS
):
    api = FastAPI(title="Gold labelling")
    order = order_of(rows)
    policy = POLICY.read_text()
    rules = RULE.findall(policy)

    def mine(row: dict) -> dict | None:
        found = [
            r
            for r in saved(out[row["split"]])
            if r["article_id"] == row["article_id"] and r["labeller"] == labeller
        ]
        return found[-1] if found else None

    def next_unlabelled() -> str | None:
        done = {
            r["article_id"]
            for p in out.values()
            for r in saved(p)
            if r["labeller"] == labeller
        }
        return next((f"/article/{aid}" for aid in order if aid not in done), None)

    @api.get("/", response_class=HTMLResponse)
    def index():
        done = {
            r["article_id"]
            for p in out.values()
            for r in saved(p)
            if r["labeller"] == labeller
        }
        listed = "".join(
            f'<tr><td>{i}</td><td><a href="/article/{aid}">{escape(aid)}</a></td>'
            f"<td>{rows[aid]['split']}</td><td>{escape(rows[aid].get('date') or '')}</td>"
            f"<td>{'✓' if aid in done else ''}</td></tr>"
            for i, aid in enumerate(order, 1)
        )
        return (
            f"<!doctype html><meta charset=utf-8><title>Gold labelling</title><style>{STYLE}"
            f"</style><p>{len(done & set(order))} of {len(order)} labelled by "
            f"{escape(labeller)}. <a href='{next_unlabelled() or '/'}'>Next unlabelled</a></p>"
            f"<table>{listed}</table>"
        )

    @api.get("/article/{article_id}", response_class=HTMLResponse)
    def article(article_id: str):
        row = rows.get(article_id)
        if row is None:
            raise HTTPException(404, "not a gold or dev article")
        try:
            if not (row.get("scan") and row.get("bbox_list")):
                raise LookupError("the article has no scan or no boxes")
            _, paths = crops_for(
                row["member"], row["scan"], row["bbox_list"], text=row.get("text")
            )
            shown = "".join(f'<img src="/crop/{p.name}" alt="crop">' for p in paths)
        except (LookupError, ValueError, httpx.HTTPError) as error:
            shown = f'<p class="error">No crop: {escape(str(error))}</p>'
        label = mine(row) or {}
        kinds = "".join(
            f'<label><input type="radio" name="kind" value="{k}"'
            f"{' checked' if label.get('kind') == k else ''}> {k}</label> "
            for k in KINDS
        )
        people = label.get("people") or [None]
        persons = "".join(box("person", p, kind="person") for p in people)
        fields = "".join(
            box(name, label.get(name), CHOICES.get(name)) for name in FIELDS
        )
        checks = "".join(
            f'<label><input type="checkbox" name="rule" value="{n}"'
            f"{' checked' if int(n) in (label.get('rules') or []) else ''}> {n}. "
            f"{escape(title)}</label><br>"
            for n, title in rules
        )
        slices = "".join(
            f'<label><input type="checkbox" name="slice" value="{name}"'
            f"{' checked' if name in (label.get('slices') or []) else ''}> {name}: "
            f"{escape(title)}</label><br>"
            for name, title in SLICES.items()
        )
        kind_quote = escape(label.get("kind_quote") or "", quote=True)
        return f"""<!doctype html><meta charset=utf-8><title>{escape(article_id)}</title>
<style>{STYLE}</style><main>
<section><p><a href="/">All articles</a> · {escape(row.get("paper") or "")} ·
{escape(row.get("date") or "")} · {row["split"]}</p><h3>{escape(row.get("headline") or "")}</h3>
<div id="text">{escape(row.get("text") or "")}</div></section>
<section>{shown}</section>
<section><form id="form" data-id="{escape(article_id, quote=True)}" onsubmit="return false">
<p>{kinds}</p><p>shown by <input name="kind_quote" class="quote" value="{kind_quote}">
<button type="button" class="take">⇐ selection</button></p>
<h4>For a report</h4>{fields}<div id="people">{persons}</div>
<button type="button" id="add">Add a person</button>
<h4>Rules applied</h4><p>{checks}</p>
<h4>Edge-case slices</h4><p>{slices}</p>
<p><label><input type="checkbox" name="crop_used"{" checked" if label.get("crop_used") else ""}>
the crop was needed</label></p>
<p><textarea name="note" rows="2" cols="50">{escape(label.get("note") or "")}</textarea></p>
<p><button type="button" id="save">Save</button> <span id="result"></span></p></form>
<details><summary>POLICY.md</summary><pre>{escape(policy)}</pre></details></section>
</main><script>{SCRIPT}</script>"""

    @api.get("/crop/{name}")
    def crop(name: str):
        path = crop_dir / name
        if not CROP.fullmatch(name) or not path.exists():
            raise HTTPException(404, "no such crop")
        return FileResponse(path, media_type="image/jpeg")

    @api.post("/label")
    def label(body: dict):
        row = rows.get(body.get("article_id"))
        if row is None:
            raise HTTPException(404, "not a gold or dev article")
        try:
            record = checked(body, row, labeller)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        save(out[row["split"]], record)
        return {"saved": record["article_id"], "next": next_unlabelled()}

    return api


if __name__ == "__main__":
    run, *rest = sys.argv[1:] or ["serve"]
    rows = articles()
    if run == "serve":
        uvicorn.run(
            app(rows, rest[0] if rest else "Claude"), host="127.0.0.1", port=8765
        )
    elif run == "crops":
        found = warm(rows)
        print(
            len(found),
            "articles,",
            sum("crops" in v for v in found.values()),
            "cropped",
        )
    elif run == "show":
        split, count, *who = rest
        print(show(rows, who[0] if who else "Claude", split, int(count)))
    elif run in ("check", "save"):
        path, *who = rest
        errors = save_file(
            Path(path), rows, who[0] if who else "Claude", dry=run == "check"
        )
        print("\n".join(errors) or "every label passes checked()")
        sys.exit(1 if errors else 0)
