"""The prefilter's lexicons: ghost terms that make an article a candidate, and near-miss
terms that put an article without one into the recall pool (ARCHITECTURE section 3.1).

Each pattern takes the common OCR misreadings: long s read as f, h as b or li, o as c or 0,
t as l or 1, and n as u. Recall comes first; triage and the reader handle precision.
"""

import re

VERSION = "v1"

GHOST = {
    "ghost": r"[gq](?:h|b|li)[oc0][sf][tl1i](?:s|ly|-?like)?",
    "apparition": r"ap?par[il1][tl1i][il1][oc0][nu]s?",
    "spectre": r"[sf]p[ec]c[tl1](?:r[ec]s?|[ec]rs?|ral)",
    "phantom": r"(?:p[hb]|f)a[nu][tl1](?:[oc0](?:m|rn|in)|asm)s?",
    "haunt": r"[hb]a[uon][nu][tl1](?:ed|ing|s)?",
    "spook": r"[sf]p[o0]{2}k(?:s|y|ed)?",  # not c: "spcck" is nearly always a misread speck
    "wraith": r"wra[il1][tl1][hb]s?",
    "poltergeist": r"po[l1i][tl1]erge[il1][sf][tl1]s?",
    "banshee": r"ban[sf]hees?",
    "goblin": r"(?:hob)?gobl[il1]ns?",
    # the 1850s spirit noises: most Stratford knockings reports use no ghost word at all.
    # The i may be lost, and the word may break across a line with no hyphen ("knock\nings").
    "knocking": (
        r"k[nu][oc0][ce]k(?:\s*\n\s*)?(?:[il1]?(?:n|u|y|ri)|m)gs"
        r"|(?:mysterious|strange|spirit|unaccountable)[\s-]+k[nu][oc0]ck(?:ing|s)"
    ),
    "rapping": (
        r"rapp(?:\s*\n\s*)?[il1]?(?:n|u|ri)gs|rappers|[sf]pirit[\s-]+rapp(?:ing|er)s?"
    ),
}

NEAR_MISS = {
    "knock": r"k[nu][oc0]ck(?:s|ed|ing)?",
    "rap": r"rapp(?:ing|ed)",
    "noise": r"(?:strange|mysterious|unaccountable|unearthly|unnatural)[\s-]+(?:noise|sound)s?",
    "spirit": r"[sf]pirits?",
    "spiritualism": r"[sf]piritual(?:ism|ists?)",
    "seance": r"s[eé]ances?",
    "supernatural": r"[sf]upernatural",
}


def _matcher(terms):
    alternatives = "|".join(f"(?P<{term}>{pattern})" for term, pattern in terms.items())
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


GHOST_MATCHER, NEAR_MISS_MATCHER = _matcher(GHOST), _matcher(NEAR_MISS)


def _find(matcher, text):
    found = {}
    # rejoin words hyphenated at a line end before matching
    for match in matcher.finditer(text.replace("-\n", "")):
        form = " ".join(match.group().lower().split())
        found.setdefault(match.lastgroup, set()).add(form)
    return {term: sorted(forms) for term, forms in found.items()}


def ghost_terms(text):
    """Each ghost term in the text, with the spellings it was scanned as."""
    return _find(GHOST_MATCHER, text)


def near_miss_terms(text):
    """Each near-miss term in the text, with the spellings it was scanned as."""
    return _find(NEAR_MISS_MATCHER, text)
