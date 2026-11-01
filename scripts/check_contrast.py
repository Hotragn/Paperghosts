"""The Morgue's text colours against their backgrounds, in both lights, read from the CSS tokens in
web/src/index.css: each pair's WCAG contrast ratio, and a failure below AA's 4.5:1 for text.

  uv run python scripts/check_contrast.py
"""

import re
import sys

from label_gold import ROOT

CSS = ROOT / "web" / "src" / "index.css"
# (text, background) as the page pairs them; a mark is lamp light laid over the card
PAIRS = [
    ("text", "bg"),
    ("text", "card"),
    ("text", "envelope"),
    ("muted", "card"),
    ("muted", "envelope"),
    ("stamp-ink", "envelope"),
    ("stamp-ink", "card"),
    ("link", "card"),
    ("link", "bg"),
    ("text", "mark@card"),
]


def tokens(css: str, selector: str) -> dict:
    block = re.search(re.escape(selector) + r"\s*\{(.*?)\}", css, re.DOTALL)[1]
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", block))


def resolved(name: str, light: dict, base: dict) -> str:
    value = light.get(name, base.get(name))
    while value.startswith("var("):
        value = light.get(value[6:-1], base.get(value[6:-1]))
    return value


def rgb(value: str, under: tuple | None = None) -> tuple:
    if value.startswith("#"):
        return tuple(int(value[i : i + 2], 16) for i in (1, 3, 5))
    r, g, b, a = map(float, re.findall(r"[\d.]+", value))
    return tuple(
        round(a * x + (1 - a) * y) for x, y in zip((r, g, b), under, strict=True)
    )


def ratio(a: tuple, b: tuple) -> float:
    def lum(c):
        c = [x / 255 for x in c]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def checked(css: str) -> list:
    base = tokens(css, ":root")
    found = []
    for lights, light in (("on", {}), ("off", tokens(css, ":root[data-lights='off']"))):
        for fg, bg in PAIRS:
            if "@" in bg:
                over, under = bg.split("@")
                back = rgb(
                    resolved(over, light, base), rgb(resolved(under, light, base))
                )
            else:
                back = rgb(resolved(bg, light, base))
            found.append(
                (lights, fg, bg, round(ratio(rgb(resolved(fg, light, base)), back), 2))
            )
    return found


def main() -> None:
    found = checked(CSS.read_text())
    for lights, fg, bg, r in found:
        print(
            f"lights {lights:3}  {fg:10} on {bg:10} {r:5.2f}  {'AA' if r >= 4.5 else 'FAIL'}"
        )
    if any(r < 4.5 for *_, r in found):
        sys.exit(1)


if __name__ == "__main__":
    main()
