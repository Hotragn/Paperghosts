"""Library of Congress title strings, such as `Eureka daily sentinel. [volume] (Eureka, Nev.)
1871-1887`: the title, the place and the state as printed, what the cataloguer supplied in
brackets, and the years (decision 34).

The place part is split on its top-level commas, and a bracket goes with the part it follows:
- after the place, a bracket adds to it: `(Honolulu [Oahu, Hawaii])` supplies the state
- after the state, or marked `i.e.`, it supplies a place: `(Bannock City, I.T. [Idaho City,
  Idaho])` and `(Juliet [i.e. Joliet], Ill.)`
- on its own, it supplies the whole place: `([Nashville, Tenn.])`
- `[sic]` affirms what's printed
A single part is the place, unless it's an abbreviated state, so `(Washington [D.C.])` and
`(New York [N.Y.])` are cities.
"""

import html
import re
import unicodedata

YEARS = re.compile(r"\s*\b(?P<first>[\d?]{4})-(?P<last>[\d?]{4}|current)\s*$")
MARKER = re.compile(r"\s*\[(?:volume|microfilm reel)\]\s*$")
BRACKET = re.compile(r"\[([^\]]*)\]")
INNER = re.compile(r"\(([^()]*)\)")

# each modern state's printed forms, beside its full name and its abbreviation in ABBREVIATIONS
FORMS = {
    "Alabama": ["Alab."],
    "Alaska": ["Alas.", "Alaska Territory", "Territory of Alaska"],
    "Arizona": ["A.T.", "Ariz. Territory", "Arizona Territory", "Ariz. T."],
    "California": ["Cal."],
    "Colorado": ["Col.", "Colorado Territory"],
    "Connecticut": ["Ct."],
    "Florida": ["Flor."],
    "Hawaii": ["H.I.", "T.H.", "H.T.", "Hawaiian Islands", "Territory of Hawaii"],
    "Idaho": ["Ida.", "Idaho Territory", "Idaho T."],
    "Illinois": ["Ills."],
    "Iowa": ["Ia."],
    "Kansas": ["Kans.", "Kas.", "Kansas Territory", "K.T."],
    "Maine": ["Me."],
    "Michigan": ["Mi."],
    "Minnesota": ["Minn. Territory", "Minnesota Territory"],
    "Montana": ["Montana Territory", "Mont. Territory", "Mont. T."],
    "Nebraska": ["Nebr.", "Nebraska Territory", "Neb. Territory"],
    "Nevada": ["Nevada Territory"],
    "New Mexico": ["N. Mex.", "Nuevo México", "New Mexico Territory", "N.M. Territory"],
    "North Dakota": ["N. Dak.", "Nord-Dakota"],
    "Ohio": ["O."],
    "Oklahoma": [
        "O.T.",
        "Oklahoma Territory",
        "Okla. Territory",
        "Ind. T.",
        "Indian Territory",
    ],
    "Oregon": ["Or.", "Oreg.", "Oregon Territory"],
    "Pennsylvania": ["Penn.", "Penna."],
    "Puerto Rico": ["Porto Rico"],
    "South Carolina": ["South-Carolina"],
    "South Dakota": ["S. Dak.", "Süd-Dakota", "Süd=Dakota"],
    "Texas": ["Tex."],
    "Utah": ["Utah Territory", "U.T."],
    "Washington": ["Washington Territory", "Wash. Territory", "Wash. T."],
    "West Virginia": ["W. Va."],
    "Wisconsin": ["Wisc.", "Wisconsin Territory"],
    "Wyoming": ["Wyoming Territory", "Wyo. Territory"],
}
ABBREVIATIONS = {
    "Alabama": "Ala.", "Alaska": "Alaska", "Arizona": "Ariz.", "Arkansas": "Ark.",
    "California": "Calif.", "Colorado": "Colo.", "Connecticut": "Conn.", "Delaware": "Del.",
    "District of Columbia": "D.C.", "Florida": "Fla.", "Georgia": "Ga.", "Hawaii": "Hawaii",
    "Idaho": "Idaho", "Illinois": "Ill.", "Indiana": "Ind.", "Iowa": "Iowa", "Kansas": "Kan.",
    "Kentucky": "Ky.", "Louisiana": "La.", "Maine": "Maine", "Maryland": "Md.",
    "Massachusetts": "Mass.", "Michigan": "Mich.", "Minnesota": "Minn.",
    "Mississippi": "Miss.", "Missouri": "Mo.", "Montana": "Mont.", "Nebraska": "Neb.",
    "Nevada": "Nev.", "New Hampshire": "N.H.", "New Jersey": "N.J.", "New Mexico": "N.M.",
    "New York": "N.Y.", "North Carolina": "N.C.", "North Dakota": "N.D.", "Ohio": "Ohio",
    "Oklahoma": "Okla.", "Oregon": "Ore.", "Pennsylvania": "Pa.", "Puerto Rico": "P.R.",
    "Rhode Island": "R.I.", "South Carolina": "S.C.", "South Dakota": "S.D.",
    "Tennessee": "Tenn.", "Texas": "Texas", "Utah": "Utah", "Vermont": "Vt.",
    "Virgin Islands": "V.I.", "Virginia": "Va.", "Washington": "Wash.",
    "West Virginia": "W.Va.", "Wisconsin": "Wis.", "Wyoming": "Wyo.",
}  # fmt: skip
# a territory's initials that stood for two: W.T. for Washington or Wisconsin, N.T. for
# Nebraska or Nevada, I.T. for Idaho or Indian Territory, and Dakota for both Dakotas
AMBIGUOUS = ["Dakota", "D.T.", "Dakota Territory", "W.T.", "N.T.", "I.T."]


def key(text):
    return re.sub(r"[^a-zà-ÿ]", "", unicodedata.normalize("NFC", text).lower())


STATES = {
    key(form): state
    for state, abbreviation in ABBREVIATIONS.items()
    for form in [state, abbreviation, *FORMS.get(state, [])]
}
STATES |= {key(form): None for form in AMBIGUOUS}


def mended(text):
    """Undoes UTF-8 that was read as Windows-1252, as in `SuÌˆd-Dakota` for `Süd-Dakota`."""
    if not re.search("[ÃÂÌËÅâ]", text):
        return text
    raw = bytearray()
    for char in text:
        try:
            raw += char.encode("cp1252")
        except UnicodeEncodeError:
            if ord(char) > 255:
                return text
            raw.append(
                ord(char)
            )  # a byte Windows-1252 leaves undefined, passed through
    try:
        return unicodedata.normalize("NFC", raw.decode("utf-8"))
    except UnicodeDecodeError:
        return text


def is_state(text):
    return text is not None and key(re.split(r"&| and ", text)[0]) in STATES


def state_name(printed):
    """The modern state a printed state names, or None where it could be two."""
    if not printed:
        return None
    return STATES.get(key(re.split(r"&| and ", printed)[0]))


def split_top(text, mark):
    """text split at each `mark` outside brackets and parentheses."""
    parts, depth, start = [], 0, 0
    for i, char in enumerate(text):
        if char in "[(":
            depth += 1
        elif char in "])":
            depth -= 1
        elif char == mark and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    return [*parts, text[start:]]


def outer_group(text):
    """What comes before the parenthesized group that ends text, and that group's inside."""
    if not text.endswith(")"):
        return text, None
    depth = 0
    for i in range(len(text) - 1, -1, -1):
        if text[i] == ")":
            depth += 1
        elif text[i] == "(":
            depth -= 1
            if depth == 0:
                return text[:i].rstrip(), text[i + 1 : -1]
    return text, None


def parse_place(text):
    found = dict.fromkeys(
        ("place", "county", "state", "supplied_place", "supplied_state")
    )
    if text is None:
        return found
    segments = []
    for raw in split_top(split_top(text, ";")[0], ","):
        brackets = BRACKET.findall(raw)
        printed = BRACKET.sub(" ", raw)
        inner = INNER.findall(printed)
        printed = " ".join(INNER.sub(" ", printed).split())
        segments.append((printed, brackets, inner))
    printed = [p for p, _, _ in segments if p]
    if len(printed) >= 2 and is_state(printed[-1]):
        found["place"], found["state"] = printed[0], printed[-1]
        found["county"] = ", ".join(printed[1:-1]) or None
    elif len(printed) >= 2:
        found["place"], found["county"] = printed[0], ", ".join(printed[1:])
    elif printed:
        words = printed[0].split()
        for cut in range(1, min(3, len(words) - 1) + 1):
            if is_state(" ".join(words[-cut:])):
                found["place"], found["state"] = (
                    " ".join(words[:-cut]),
                    " ".join(words[-cut:]),
                )
                break
        else:
            if "." in printed[0] and is_state(printed[0]):
                found["state"] = printed[0]
            else:
                found["place"] = printed[0]
    for printed_part, brackets, inner in segments:
        for note in inner:
            if found["state"] is None and is_state(note):
                found["state"] = note
        for content in brackets:
            correction = content.startswith("i.e.")
            content = content.removeprefix("i.e.").strip()
            if content == "sic" or not content:
                continue
            parts = [p.strip() for p in split_top(content, ",") if p.strip()]
            parts = [p.removeprefix("i.e.").strip() for p in parts]
            after_place = printed_part and printed_part == found["place"]
            after_state = printed_part and printed_part == found["state"]
            if len(parts) > 1 and after_place and not correction:
                found["supplied_state"] = parts[-1] if is_state(parts[-1]) else None
            elif len(parts) > 1 and after_state and is_state(parts[0]):
                # "Dakota [Dakota Territory, i.e. S.D.]": the territory, then its state
                found["supplied_state"] = parts[-1]
            elif len(parts) > 1:
                found["supplied_place"] = parts[0]
                if is_state(parts[-1]):
                    found["supplied_state"] = parts[-1]
            elif is_state(content) and not (correction and after_place):
                found["supplied_state"] = content
            else:
                found["supplied_place"] = content
    return found


def year(text):
    return int(text) if text.isdigit() else None


def parse_title(paper):
    """A title string's title, place, county, state as printed, what was supplied, and its
    years: the printed span, and the first and last year where they are known."""
    text = mended(html.unescape(paper or "")).strip()
    years = YEARS.search(text)
    if years:
        text = text[: years.start()].rstrip()
    head, place = outer_group(text)
    return {
        "title": MARKER.sub("", head).strip(),
        **parse_place(place),
        "years": years and f"{years['first']}-{years['last']}",
        "first_year": years and year(years["first"]),
        "last_year": years and year(years["last"]),
    }


def then_and_now(title, modern):
    """The place as printed, and its modern state where that differs: "Charlestown, Va. (now
    W.Va.)". None for a title that names no place."""
    place = title["place"] or title["supplied_place"]
    state = title["state"] or title["supplied_state"]
    if place is None or state is None:
        return None
    shown = f"{place}, {state}"
    if modern and state_name(state) != modern:
        shown += f" (now {ABBREVIATIONS[modern]})"
    return shown
