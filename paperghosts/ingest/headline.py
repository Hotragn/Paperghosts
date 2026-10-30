"""The headline as the site shows it: the OCR's headline without the masthead lines that an
article's first box often takes in, which lead it. The stored OCR keeps them."""

import datetime
import html
import itertools
import re

# a weekday or month, and a time of day, as a masthead's dateline prints them
WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
MONTH_WORDS = (
    r"\b(?:january|february|march|april|may|june|july|august|september|october"
    r"|november|december|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)\b"
)
DATE_WORDS = re.compile(rf"\b(?:{'|'.join(WEEKDAYS)})\b|{MONTH_WORDS}", re.IGNORECASE)
TIMES = re.compile(r"\b(?:morning|evening)\b", re.IGNORECASE)
ISSUE_WORDS = re.compile(
    r"\b(?:new|series|vol|volume|no|number|whole|page)\b", re.IGNORECASE
)
VOLUME = re.compile(r"\b(?:vol|volume)\b", re.IGNORECASE)
# numbers as printed and as OCR misreads them (I or l for 1, O for 0), and roman numerals
NUMERALS = re.compile(r"\b(?:[\dIilOo]+|[IVXLCDM]+)\b")
DIGITS = str.maketrans("IilOo", "11100")
MONTHS = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]
# the day after a month ('OCTOBER 31', 'April 4th'), and a year from 1600 to 1999
DAY = re.compile(
    MONTH_WORDS + r"\W{0,3}([\dIilOo]{1,2})(?:st|nd|rd|th|d)?(?!\w)", re.IGNORECASE
)
YEAR = re.compile(r"(?<!\w)([1Il][6-9][\dIilOo]{2})(?!\w)")


def letters(text):
    return re.sub(r"[^a-z]", "", text.lower())


def spelled(word):
    """These letters with anything but letters between them, since OCR splits a
    masthead's wide lettering: 'portland' matches 'PORTL AND'."""
    return r"[\W\d_]*".join(map(re.escape, word))


def names(paper):
    """The paper's title, with or without 'The', and its place with or without its state,
    from the LoC title: 'The national era. [volume] (Washington [D.C.]) 1847-1860' gives
    national era, and Washington or Washington D.C. Either is None if the title lacks it."""
    paper = html.unescape(paper or "")
    title = letters(paper.split("[")[0].split("(")[0]).removeprefix("the")
    found = [None, None]
    if title:
        found[0] = alone(rf"(?:{spelled('the')}[\W\d_]*)?{spelled(title)}", title)
    place = re.search(r"\(\[?([^,\[\])]+)[,\s\[]*([^\])]*)", paper)
    if place and letters(place[1]):
        state = letters(place[2])
        state = rf"(?:[\W\d_]*{spelled(state)})?" if state else ""
        found[1] = alone(spelled(letters(place[1])) + state, letters(place[1]))
    return [name and re.compile(name, re.IGNORECASE) for name in found]


def alone(pattern, name):
    """A short name must stand alone: 'post' is inside 'PoStry' (Poetry) and 'iola' inside
    'VIOLA'. A longer one needn't, since OCR runs stray letters into mastheads
    ('NMEMPHIs') and a line still needs all but two of its letters accounted for."""
    return rf"(?<![a-z]){pattern}(?![a-z])" if len(name) < 6 else pattern


def issue_date(date):
    try:
        return datetime.date.fromisoformat(date or "")
    except ValueError:
        return None


def number(text):
    digits = text.translate(DIGITS)
    return int(digits) if digits.isdigit() else None


def on_issue_date(line, issue):
    """Whether the date on the line is the issue's own. Each weekday and month on it must be
    the issue's. Then the issue's weekday settles it, since OCR misreads digits far more
    often than words ('SUNDAY. DECEMBER 9.' for the 6th). Without a weekday, the day after a
    month and the year must be the issue's too, with OCR's I, l and O read as digits."""
    if issue is None:
        return False
    words = [word.lower() for word in DATE_WORDS.findall(line)]
    weekdays = [word for word in words if word in WEEKDAYS]
    if any(WEEKDAYS.index(word) != issue.weekday() for word in weekdays) or any(
        MONTHS.index(word[:3]) + 1 != issue.month
        for word in words
        if word not in WEEKDAYS
    ):
        return False
    return bool(weekdays) or (
        all(number(day) == issue.day for day in DAY.findall(line))
        and all(number(year) == issue.year for year in YEAR.findall(line))
    )


def kind(line, title, place, issue):
    """What makes a line a masthead line, give or take numbers and two stray letters, or None:
    - "title", or "volume" for a numbered volume line, which let number lines beside them go
    - "masthead" for the paper's own place, or a date that is the issue's own
    - "number" for a number, or a numbered issue line, which go only beside the title or volume
    A weekday or month alone isn't a date (it heads listings, and poems are named for months)
    unless the paper's name is beside it. A date that isn't the issue's belongs to the article
    ('April 4th.' in an advertisement of the 11th), and so does In and the paper's place ('IN
    DETROIT' titles a column)."""
    if not letters(line):
        years = {number(year) for year in YEAR.findall(line)}
        if years:
            return "masthead" if issue and years == {issue.year} else None
        return "number"
    if place and re.match(r"\W*in\b", line, re.IGNORECASE) and place.search(line):
        return None
    rest, named = line, set()
    for name, pattern in (("title", title), ("place", place)):
        if pattern:
            rest, matches = pattern.subn(" ", rest)
            if matches:
                named.add(name)
    numbered = bool(re.search(r"\d", rest) or NUMERALS.search(rest))
    dates = len(DATE_WORDS.findall(rest))
    times = len(TIMES.findall(rest)) if dates else 0
    dated = dates + times >= 2 or bool(dates and (numbered or named))
    if dated:
        if not on_issue_date(rest, issue):
            return None
        rest = TIMES.sub(" ", DATE_WORDS.sub(" ", rest))
    issued = numbered and bool(ISSUE_WORDS.search(rest))
    volume = issued and bool(VOLUME.search(rest))
    if issued:
        rest = ISSUE_WORDS.sub(" ", rest)
    if len(letters(NUMERALS.sub(" ", rest))) > 2:
        return None
    if "title" in named:
        return "title"
    if volume:
        return "volume"
    if "place" in named or dated:
        return "masthead"
    return "number" if issued else None


def masthead_lines(headline, paper, date):
    """Each line of the headline that isn't blank, and whether the site drops it. Masthead
    lines go only while they lead: a dated line further down belongs to the article ('Out
    Ghosts Next / Monday Evening'). A number line goes only when the leading lines hold the
    paper's title or its volume ('NO. XXXVI.' alone numbers an essay). Rules and stray marks
    go anywhere."""
    title, place = names(paper)
    issue = issue_date(date)
    lines = [line.strip() for line in (headline or "").splitlines() if line.strip()]
    marks = [not letters(line) and not re.search(r"\d", line) for line in lines]
    kinds = [
        None if mark else kind(line, title, place, issue)
        for line, mark in zip(lines, marks, strict=True)
    ]
    leading = itertools.takewhile(
        bool, (found for found, mark in zip(kinds, marks, strict=True) if not mark)
    )
    beside = bool({"title", "volume"} & set(leading))
    leading = True
    for line, mark, found in zip(lines, marks, kinds, strict=True):
        if mark or (leading and found and (found != "number" or beside)):
            yield line, True
        else:
            leading = False
            yield line, False


def display_headline(headline, paper, date):
    return "\n".join(
        line for line, dropped in masthead_lines(headline, paper, date) if not dropped
    )
