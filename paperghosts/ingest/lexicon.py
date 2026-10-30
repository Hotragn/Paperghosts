"""The prefilter's lexicons: ghost terms that make an article a candidate, and near-miss
terms that put an article without one into the recall pool (ARCHITECTURE section 3.1).

Each pattern takes the common OCR misreadings: long s read as f, h as b or li, o as c or 0,
t as l or 1, and n as u. Recall comes first; triage and the reader handle precision.

Version 2 adds the spiritualist words of the reports version 1 missed (decisions 30 and 31).
Its terms only add candidates: every version 1 candidate stays one.
"""

import re

VERSION = "v2"

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
    # v2: spirit communications, spirit control and the medium's tools
    "spiritualism": r"[sf]piritual(?:is[mt]s?|istic)",
    "seance": r"s[eé]ances?",
    "spirit_phrase": (
        r"[sf]pirits?[\s-]+(?:world|land|control|communications?|manifestations?|messages?"
        r"|photographs?|circles?|mediums?)"
        r"|control(?:led)?\s+(?:of|by)\s+(?:the\s+)?[sf]pirits?|disembodied"
        r"|[sf]pirits?\s+of\s+the\s+(?:dead|departed)"
    ),
    "ouija": r"ouija|planchette",
}

# v2: terms whose words need only share the article, since a medium's report spreads them
TOGETHER = {"spirit+medium": (r"[sf]pirits?", r"mediums?")}

NEAR_MISS = {
    "knock": r"k[nu][oc0]ck(?:s|ed|ing)?",
    "rap": r"rapp(?:ing|ed)",
    "noise": r"(?:strange|mysterious|unaccountable|unearthly|unnatural)[\s-]+(?:noise|sound)s?",
    "spirit": r"[sf]pirits?",
    "spiritualism": r"[sf]piritual(?:ism|ists?)",
    "seance": r"s[eé]ances?",
    "supernatural": r"[sf]upernatural",
}


def matcher(terms):
    alternatives = "|".join(f"(?P<{term}>{pattern})" for term, pattern in terms.items())
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


GHOST_MATCHER, NEAR_MISS_MATCHER = matcher(GHOST), matcher(NEAR_MISS)
_TOGETHER = {
    term: [re.compile(rf"\b(?:{word})\b", re.IGNORECASE) for word in words]
    for term, words in TOGETHER.items()
}

# The pre-check folds most OCR confusion classes above to one letter (q→g, b→h, c 0→o,
# f→s, i 1 t→l, u→n). Every match of a term then contains one of its stems, so an article
# with none of them can skip the regex. Stems are long enough to pass over the commonest
# lookalikes in 1850: "throughout" (gho), "sarsaparilla" (aparll) and "annual" (nnnal).
FOLD = str.maketrans("qbc0fi1tu", "ghoosllln")
GHOST_STEMS = {
    "ghost": ("ghos", "gllos"),
    "apparition": ("parlllo",),
    "spectre": ("speolr", "speoler", "speolor", "spoolr", "spooler", "spoolor"),
    "phantom": ("phanl", "sanlo", "sanlas"),
    "haunt": ("hannl", "haonl"),
    "spook": ("spook",),
    "wraith": ("wrall",),
    "poltergeist": ("pollerg",),
    "banshee": ("hansh",),
    "goblin": ("gohll",),
    "knocking": ("knook", "knoek"),
    "rapping": ("rapp",),
    "spiritualism": ("splrlln",),
    "seance": ("seano", "séano"),
    "spirit_phrase": ("splrl", "dlsemho"),
    "ouija": ("onlja", "planohe"),
    "spirit+medium": ("splrl",),
}
NEAR_MISS_STEMS = {
    "knock": ("knook",),
    "rap": ("rapp",),
    "noise": ("slrang", "mysler", "nnaooo", "nnearl", "nnnalnr"),
    "spirit": ("splrl",),
    "spiritualism": ("splrl",),
    "seance": ("seano", "séano"),
    "supernatural": ("snpern",),
}


_GHOST_STEMS = tuple(stem for group in GHOST_STEMS.values() for stem in group)
_NEAR_MISS_STEMS = tuple(stem for group in NEAR_MISS_STEMS.values() for stem in group)


def _find(matcher, stems, text, precheck, together=None):
    text = text.replace("-\n", "")  # rejoin words hyphenated at a line end
    if precheck:
        folded = text.lower().translate(FOLD)
        if not any(stem in folded for stem in stems):
            return {}
    found = {}
    for match in matcher.finditer(text):
        form = " ".join(match.group().lower().split())
        found.setdefault(match.lastgroup, set()).add(form)
    for term, words in (together or {}).items():
        forms = [
            {match.group().lower() for match in word.finditer(text)} for word in words
        ]
        if all(forms):
            found[term] = set().union(*forms)
    return {term: sorted(forms) for term, forms in found.items()}


def ghost_terms(text, precheck=True):
    """Each ghost term in the text, with the spellings it was scanned as."""
    return _find(GHOST_MATCHER, _GHOST_STEMS, text, precheck, _TOGETHER)


def near_miss_terms(text, precheck=True):
    """Each near-miss term in the text, with the spellings it was scanned as."""
    return _find(NEAR_MISS_MATCHER, _NEAR_MISS_STEMS, text, precheck)
