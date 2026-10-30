"""Eval A's charts, as standalone SVG files with a light and a dark theme and a tooltip on
every mark. They follow the dataviz rules: one axis, thin marks with rounded data ends,
recessive grid lines, and text in ink colors, never in a series color."""

import math
from html import escape

STYLE = """<style>
.bg{fill:#fcfcfb}.ink{fill:#0b0b0b}.muted{fill:#52514e}.grid{stroke:#e6e5e1;stroke-width:1}
.axis{stroke:#c3c2b7;stroke-width:1}.s1{fill:#2a78d6}.s2{fill:#eb6834}.wash{fill:#2a78d6;fill-opacity:.1}
.line{fill:none;stroke:#2a78d6;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.whisker{stroke:#0b0b0b;stroke-width:1.5}.hit{fill:transparent}
text{font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;font-size:12px}
.title{font-size:15px;font-weight:600}
@media (prefers-color-scheme:dark){
.bg{fill:#1a1a19}.ink{fill:#f0efec}.muted{fill:#c3c2b7}.grid{stroke:#333331}.axis{stroke:#52514e}
.s1{fill:#3987e5}.s2{fill:#d95926}.wash{fill:#3987e5}.line{stroke:#3987e5}.whisker{stroke:#f0efec}}
</style>"""
WIDTH = 760


def compact(value):
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= size:
            return f"{value / size:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{value:g}"


def nice(top, ticks=4):
    """A round upper bound and step for an axis that reaches `top`."""
    raw = max(top, 1e-9) / ticks
    power = 10 ** math.floor(math.log10(raw))
    for step in (1, 2, 2.5, 5, 10):
        if step * power >= raw:
            step *= power
            break
    return step * -(-top // step), step


def text(x, y, value, cls="ink", anchor="start", extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}" {extra}>{escape(str(value))}</text>'


def hbar(x, y, width, height, cls, tip):
    """A bar from the baseline at x, square there and rounded 4px at its data end."""
    r = min(4, width / 2, height / 2)
    path = f"M{x:.1f},{y:.1f}H{x + width - r:.1f}A{r},{r} 0 0 1 {x + width:.1f},{y + r:.1f}V{y + height - r:.1f}A{r},{r} 0 0 1 {x + width - r:.1f},{y + height:.1f}H{x:.1f}Z"
    return (
        f'<path d="{path}" class="{cls}"><title>{escape(tip)}</title></path>'
        if width > 0
        else ""
    )


def vbar(x, base, width, height, cls, tip):
    r = min(4, width / 2, height / 2)
    path = f"M{x:.1f},{base:.1f}V{base - height + r:.1f}A{r},{r} 0 0 1 {x + r:.1f},{base - height:.1f}H{x + width - r:.1f}A{r},{r} 0 0 1 {x + width:.1f},{base - height + r:.1f}V{base:.1f}Z"
    return (
        f'<path d="{path}" class="{cls}"><title>{escape(tip)}</title></path>'
        if height > 0
        else ""
    )


def page(height, title, subtitle, body, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}" role="img" aria-label="{escape(label)}">'
        f'<title>{escape(title)}</title>{STYLE}<rect class="bg" width="{WIDTH}" height="{height}"/>'
        + text(24, 30, title, "ink title")
        + text(24, 50, subtitle, "muted")
        + body
        + "</svg>\n"
    )


def bars(
    path, title, subtitle, rows, fmt, series=None, intervals=None, label_width=170
):
    """Horizontal bars: rows of (label, value) or (label, value, second value), with an
    optional text to print after the bar, and an optional 95% interval per row as (low, high)."""
    numbers = [[v for v in row[1:] if not isinstance(v, str)] for row in rows]
    saids = [
        row[-1] if isinstance(row[-1], str) else " / ".join(map(fmt, values))
        for row, values in zip(rows, numbers, strict=True)
    ]
    top = max(max(values) for values in numbers)
    top, step = nice(max([top] + [high for _, high in intervals or []]))
    # room on the right for the longest text after a bar, at about 7px a character
    left, right = 24 + label_width, WIDTH - 30 - 7 * max(map(len, saids))
    band = 22 if not series else 30
    y0 = 78 if series else 68
    scale = (right - left) / top
    body = []
    if series:
        for i, (name, cls) in enumerate(series):
            body += [
                f'<rect x="{left + i * 150}" y="58" width="12" height="12" rx="3" class="{cls}"/>',
                text(left + i * 150 + 18, 68, name, "muted"),
            ]
    height = y0 + band * len(rows) + 30
    for k in range(round(top / step) + 1):
        x = left + k * step * scale
        body += [
            f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y0 - 4}" y2="{height - 26}" class="grid"/>',
            text(x, height - 10, fmt(k * step), "muted", "middle"),
        ]
    for n, row in enumerate(rows):
        y = y0 + n * band
        body.append(text(left - 8, y + band / 2 + 4, row[0], "ink", "end"))
        values, said = numbers[n], saids[n]
        # the whole row is a hover target, so a bar of zero has a tooltip too
        body.append(
            f'<rect class="hit" x="{left}" y="{y}" width="{right - left}" height="{band}"><title>{escape(f"{row[0]}: {said}")}</title></rect>'
        )
        thick = min(24, (band - 6) / len(values))
        for i, value in enumerate(values):
            cls = series[i][1] if series else "s1"
            body.append(
                hbar(
                    left,
                    y + 3 + i * (thick + 2),
                    value * scale,
                    thick,
                    cls,
                    f"{row[0]}: {fmt(value)}",
                )
            )
        end = max(values) * scale
        if intervals:
            low, high = intervals[n]
            yc = y + 3 + thick / 2
            body += [
                f'<line x1="{left + low * scale:.1f}" x2="{left + high * scale:.1f}" y1="{yc:.1f}" y2="{yc:.1f}" class="whisker"/>',
                f'<line x1="{left + low * scale:.1f}" x2="{left + low * scale:.1f}" y1="{yc - 5:.1f}" y2="{yc + 5:.1f}" class="whisker"/>',
                f'<line x1="{left + high * scale:.1f}" x2="{left + high * scale:.1f}" y1="{yc - 5:.1f}" y2="{yc + 5:.1f}" class="whisker"/>',
            ]
            end = high * scale
        body.append(text(left + end + 6, y + band / 2 + 4, said, "muted"))
    path.write_text(page(height, title, subtitle, "".join(body), title))
    return path


def columns(path, title, subtitle, rows, fmt, marker=None):
    """Vertical columns: rows of (label, value, tooltip). marker, if given, is (index, label)
    for a hairline at a column, such as the median."""
    left, right, base, top_y = 70, WIDTH - 24, 300, 70
    top, step = nice(max(r[1] for r in rows))
    scale = (base - top_y) / top
    slot = (right - left) / len(rows)
    width = min(24, slot - 2)
    body = []
    for k in range(round(top / step) + 1):
        y = base - k * step * scale
        body += [
            f'<line x1="{left}" x2="{right}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>',
            text(left - 8, y + 4, fmt(k * step), "muted", "end"),
        ]
    for i, (label, value, tip) in enumerate(rows):
        x = left + i * slot + (slot - width) / 2
        body.append(vbar(x, base, width, value * scale, "s1", tip))
        if len(rows) <= 12 or i % 2 == 0:
            body.append(text(x + width / 2, base + 16, label, "muted", "middle"))
    if marker:
        index, label = marker
        x = left + index * slot + slot / 2
        body += [
            f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top_y - 6}" y2="{base}" class="axis"/>',
            # near the right edge the label ends at the line instead of starting there
            text(x + 4, top_y - 8, label, "ink")
            if x < WIDTH - 120
            else text(x - 4, top_y - 8, label, "ink", "end"),
        ]
    body.append(
        f'<line x1="{left}" x2="{right}" y1="{base}" y2="{base}" class="axis"/>'
    )
    path.write_text(page(base + 30, title, subtitle, "".join(body), title))
    return path


def years_chart(path, by_year):
    """Two panels on one time axis: articles per year, and candidates per million articles."""
    left, right = 70, WIDTH - 24
    first, last = by_year[0]["year"], by_year[-1]["year"]
    x = lambda year: left + (year - first) / (last - first) * (right - left)
    body = []
    panels = (
        ("Articles per year", "articles", 80, 230),
        ("Candidates per million articles", "candidates_per_million", 290, 440),
    )
    for name, key, top_y, base in panels:
        top, step = nice(max(r[key] for r in by_year))
        y = lambda v, top=top, top_y=top_y, base=base: base - v / top * (base - top_y)
        body.append(text(left, top_y - 10, name, "ink"))
        for k in range(round(top / step) + 1):
            body += [
                f'<line x1="{left}" x2="{right}" y1="{y(k * step):.1f}" y2="{y(k * step):.1f}" class="grid"/>',
                text(left - 8, y(k * step) + 4, compact(k * step), "muted", "end"),
            ]
        runs, run = [], []
        for r in by_year:  # a gap in the years breaks the line
            if run and r["year"] != run[-1]["year"] + 1:
                runs.append(run)
                run = []
            run.append(r)
        runs.append(run)
        for run in runs:
            points = " ".join(f"{x(r['year']):.1f},{y(r[key]):.1f}" for r in run)
            if key == "articles" and len(run) > 1:
                body.append(
                    f'<polygon class="wash" points="{x(run[0]["year"]):.1f},{base} {points} {x(run[-1]["year"]):.1f},{base}"/>'
                )
            body.append(
                f'<polyline class="line" points="{points}"/>'
                if len(run) > 1
                else f'<circle cx="{x(run[0]["year"]):.1f}" cy="{y(run[0][key]):.1f}" r="2" class="s1"/>'
            )
        body.append(
            f'<line x1="{left}" x2="{right}" y1="{base}" y2="{base}" class="axis"/>'
        )
    for r in by_year:  # hover targets, one per year across both panels
        tip = f"{r['year']}: {r['articles']:,} articles, {r['candidates']:,} candidates, {r['candidates_per_million']:.0f} per million"
        body.append(
            f'<rect class="hit" x="{x(r["year"]) - 2:.1f}" y="70" width="4" height="372"><title>{escape(tip)}</title></rect>'
        )
    for year in range(1780, last + 1, 20):
        body.append(text(x(year), 460, year, "muted", "middle"))
    path.write_text(
        page(
            476,
            "Articles and candidates by year",
            "AmericanStories, all 180 year files; gaps are years with no file",
            "".join(body),
            "Articles and candidates by year",
        )
    )
    return path


def draw_all(report, out):
    made = [years_chart(out / "years.svg", report["by_year"])]
    states = [s for s in report["by_state"] if s["articles"] >= 1_000_000]
    states.sort(key=lambda s: -s["candidates_per_million"])
    made.append(
        bars(
            out / "states.svg",
            "Candidates per million articles, by state",
            f"States with a million articles or more; {report['no_state']['share_of_candidates']:.1%} of candidates have no state on record",
            [
                (
                    "No state on record" if s["state"] == "unknown" else s["state"],
                    s["candidates_per_million"],
                )
                for s in states
            ],
            lambda v: f"{v:,.0f}",
        )
    )
    terms = sorted(report["terms"]["any"], key=lambda t: -report["terms"]["any"][t])
    made.append(
        bars(
            out / "terms.svg",
            "Candidates by ghost term",
            "A candidate can hold several terms; 'only' counts those holding just this one",
            [(t, report["terms"]["any"][t], report["terms"]["only"][t]) for t in terms],
            compact,
            series=[("Holds the term", "s1"), ("Holds only this term", "s2")],
        )
    )
    lengths = report["lengths"]["histogram"]
    made.append(
        columns(
            out / "lengths.svg",
            "Candidate length",
            f"Words in the article's text; median {report['lengths']['p50']}",
            [
                (
                    f"{b['from']}+" if b["to"] is None else f"{b['from']}–{b['to']}",
                    b["candidates"],
                    f"{b['candidates']:,} candidates",
                )
                for b in lengths
            ],
            compact,
        )
    )
    ocr = report["ocr_quality"]
    made.append(
        columns(
            out / "ocr.svg",
            "OCR quality of candidates",
            f"Share of words a standard dictionary knows; {ocr['sample']}",
            [
                (f"{i * 5}%", n, f"{i * 5}–{i * 5 + 5}%: {n:,} candidates")
                for i, n in enumerate(ocr["histogram"])
            ],
            compact,
            marker=(min(19, int(ocr["p50"] * 20)), f"median {ocr['p50']:.0%}"),
        )
    )
    sizes = report["reprints"]["size_histogram"]
    made.append(
        columns(
            out / "reprints.svg",
            "Reprint clusters by size",
            f"{report['reprints']['clusters']:,} clusters hold {report['reprints']['clustered_candidates']:,} candidates ({report['reprints']['share_clustered']:.0%})",
            [
                (
                    f"{b['from']}+"
                    if b["to"] is None
                    else (
                        f"{b['from']}"
                        if b["from"] == b["to"]
                        else f"{b['from']}–{b['to']}"
                    ),
                    b["clusters"],
                    f"{b['clusters']:,} clusters, {b['candidates']:,} candidates",
                )
                for b in sizes
            ],
            compact,
        )
    )
    composition = report["composition"].get("categories")
    if composition:
        rows = sorted(composition.items(), key=lambda kv: -kv[1]["share"])
        made.append(
            bars(
                out / "composition.svg",
                "What the candidates are",
                f"{report['composition']['judged']} candidates at random, judged by hand; whiskers are 95% intervals",
                [
                    (
                        name.replace("_", " "),
                        c["share"] * 100,
                        f"{c['count']} ({c['share']:.1%}, {c['low']:.1%}–{c['high']:.1%})",
                    )
                    for name, c in rows
                ],
                lambda v: f"{v:.0f}%",
                intervals=[(c["low"] * 100, c["high"] * 100) for _, c in rows],
            )
        )
    recall = report["recall"]
    if composition and all("share" in recall[p] for p in ("near_miss", "random")):
        rows = [
            ("Candidates", composition["ghost_report"]),
            ("Near-miss pool", recall["near_miss"]),
            ("All non-candidates", recall["random"]),
        ]
        made.append(
            bars(
                out / "recall.svg",
                "Ghost reports in and out of the candidates",
                "Share of each pool's sample that is a ghost report, judged by hand; whiskers are 95% intervals",
                [
                    (
                        name,
                        r["share"] * 100,
                        f"{r['count']} of {r['n']} ({r['low']:.1%}–{r['high']:.1%}), {compact(r['implied_low'])}–{compact(r['implied_high'])} articles",
                    )
                    for name, r in rows
                ],
                lambda v: f"{v:.1f}%",
                intervals=[(r["low"] * 100, r["high"] * 100) for _, r in rows],
            )
        )
    return made
