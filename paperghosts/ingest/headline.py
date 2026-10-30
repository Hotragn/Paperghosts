"""The headline as the site shows it: the OCR's headline without the masthead lines that an
article's first box often takes in, which lead it. The stored OCR keeps them."""

import html
import re

# a weekday or month, and a time of day, as a masthead's dateline prints them
DATE_WORDS = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february"
    r"|march|april|may|june|july|august|september|october|november|december|jan|feb"
    r"|mar|apr|jun|jul|aug|sept?|oct|nov|dec)\b",
    re.IGNORECASE,
)
TIMES = re.compile(r"\b(?:morning|evening)\b", re.IGNORECASE)
ISSUE_WORDS = re.compile(
    r"\b(?:new|series|vol|volume|no|number|whole|page)\b", re.IGNORECASE
)
# numbers as printed and as OCR misreads them (I or l for 1, O for 0), and roman numerals
NUMERALS = re.compile(r"\b(?:[\dIilOo]+|[IVXLCDM]+)\b")


def letters(text):
    return re.sub(r"[^a-z]", "", text.lower())


def spelled(word):
    """These letters with anything but letters between them, since OCR splits a
    masthead's wide lettering: 'portland' matches 'PORTL AND'."""
    return r"[\W\d_]*".join(map(re.escape, word))


def names(paper):
    """The paper's title, with or without 'The', and its place with or without its state,
    from the LoC title: 'The national era. [volume] (Washington [D.C.]) 1847-1860' gives
    national era, and Washington or Washington D.C."""
    paper = html.unescape(paper or "")
    title = letters(paper.split("[")[0].split("(")[0]).removeprefix("the")
    found = []
    if title:
        found.append(alone(rf"(?:{spelled('the')}[\W\d_]*)?{spelled(title)}", title))
    place = re.search(r"\(\[?([^,\[\])]+)[,\s\[]*([^\])]*)", paper)
    if place and letters(place[1]):
        state = letters(place[2])
        state = rf"(?:[\W\d_]*{spelled(state)})?" if state else ""
        found.append(alone(spelled(letters(place[1])) + state, letters(place[1])))
    return [re.compile(name, re.IGNORECASE) for name in found]


def alone(pattern, name):
    """A short name must stand alone: 'post' is inside 'PoStry' (Poetry) and 'iola' inside
    'VIOLA'. A longer one needn't, since OCR runs stray letters into mastheads
    ('NMEMPHIs') and a line still needs all but two of its letters accounted for."""
    return rf"(?<![a-z]){pattern}(?![a-z])" if len(name) < 6 else pattern


def masthead(line, paper_names):
    """A line with no letters, or one that is the paper's names, a date or a numbered issue
    line, give or take numbers and two stray letters. A weekday or month alone isn't a date
    (it heads listings, and poems are named for months), unless the paper's name is beside
    it; an issue word needs a number; and numbers alone don't count ('II' is a part)."""
    if not letters(line):
        return True
    rest, found = line, False
    for pattern in paper_names:
        rest, matches = pattern.subn(" ", rest)
        found = found or matches > 0
    numbered = bool(re.search(r"\d", rest) or NUMERALS.search(rest))
    dates = len(DATE_WORDS.findall(rest))
    times = len(TIMES.findall(rest)) if dates else 0
    if dates + times >= 2 or (dates and (numbered or found)):
        rest, found = TIMES.sub(" ", DATE_WORDS.sub(" ", rest)), True
    if numbered and ISSUE_WORDS.search(rest):
        rest, found = ISSUE_WORDS.sub(" ", rest), True
    return found and len(letters(NUMERALS.sub(" ", rest))) <= 2


def masthead_lines(headline, paper):
    """Each line of the headline that isn't blank, and whether the site drops it. Masthead
    lines go only while they lead: a dated line further down belongs to the article ('Out
    Ghosts Next / Monday Evening'). Rules and stray marks go anywhere."""
    paper_names, leading = names(paper), True
    for line in (headline or "").splitlines():
        line = line.strip()
        if not line:
            continue
        marks = not letters(line) and not re.search(r"\d", line)
        if marks or (leading and masthead(line, paper_names)):
            yield line, True
        else:
            leading = False
            yield line, False


def display_headline(headline, paper):
    return "\n".join(
        line for line, dropped in masthead_lines(headline, paper) if not dropped
    )
