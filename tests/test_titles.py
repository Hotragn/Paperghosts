"""The LoC title parser: the title, the place and the state as printed, what the cataloguer
supplied in brackets, and the years. Its hard cases are one test each. tests/fixtures/titles.json
holds 200 titles drawn at random from the candidates' 3,336 LCCNs, each with its expected output
checked by hand."""

import json
from pathlib import Path

import pytest

from paperghosts.geo.titles import parse_title, state_name, then_and_now

FIXTURE = Path(__file__).parent / "fixtures" / "titles.json"


def parsed(paper, **fields):
    found = parse_title(paper)
    return {k: found[k] for k in fields}


def test_a_title_gives_its_place_state_and_years():
    found = parse_title("Eureka daily sentinel. [volume] (Eureka, Nev.) 1871-1887")

    assert found == {
        "title": "Eureka daily sentinel.",
        "place": "Eureka",
        "county": None,
        "state": "Nev.",
        "supplied_place": None,
        "supplied_state": None,
        "years": "1871-1887",
        "first_year": 1871,
        "last_year": 1887,
    }


@pytest.mark.parametrize(
    ("paper", "fields"),
    [
        # a marker after the title, of either kind
        ("Daily Kennebec journal. [microfilm reel] (Augusta, Me.) 1870-1975",
         {"title": "Daily Kennebec journal.", "place": "Augusta", "state": "Me."}),
        # the state only in brackets: supplied by the cataloguer, not printed
        ("New Orleans daily crescent. [volume] (New Orleans [La.]) 1851-1866",
         {"place": "New Orleans", "state": None, "supplied_state": "La."}),
        ("Evening star. [volume] (Washington, D.C.) 1854-1972",
         {"place": "Washington", "state": "D.C."}),
        ("National Republican. (Washington City (D.C.)) 1872-1888",
         {"place": "Washington City", "state": "D.C."}),
        # no place at all: a short form, or a title record's job
        ("The New York herald.",
         {"title": "The New York herald.", "place": None, "state": None, "years": None}),
        # a county between the place and the state, and a territory with its state supplied
        ("Devils Lake inter-ocean. (Devils Lake, Ramsey Co., Dakota [N.D.]) 1884-1905",
         {"place": "Devils Lake", "county": "Ramsey Co.", "state": "Dakota", "supplied_state": "N.D."}),
        # corrections: printed first, the correction supplied
        ("Juliet signal. [volume] (Juliet [i.e. Joliet], Ill.) 1844-1???",
         {"place": "Juliet", "supplied_place": "Joliet", "state": "Ill.", "first_year": 1844, "last_year": None}),
        ("Grant County herald. [volume] (Lancaster, W.T. [i.e. Wis.]) 1843-1844",
         {"state": "W.T.", "supplied_state": "Wis."}),
        ("Marble Hill press. (Marbel [sic] Hill, Mo.) 1881-1923",
         {"place": "Marbel Hill", "supplied_place": None}),
        # the whole place supplied
        ("Nashville union. [volume] ([Nashville, Tenn.]) 1851-1853",
         {"place": None, "state": None, "supplied_place": "Nashville", "supplied_state": "Tenn."}),
        ("Boise news. (Bannock City, I.T. [Idaho City, Idaho]) 1863-1864",
         {"place": "Bannock City", "state": "I.T.", "supplied_place": "Idaho City", "supplied_state": "Idaho"}),
        # a bracket after the state that starts with a state supplies only a state, with i.e. inside
        ("The Hot Springs star. (Hot Spings [Hot Springs], Dakota [Dakota Territory, i.e. S.D.]) 1886-189?",
         {"place": "Hot Spings", "state": "Dakota", "supplied_place": "Hot Springs", "supplied_state": "S.D."}),
        # no comma before the state, a semicolon after it, an ampersand between two
        ("Cheraw gazette and Pee Dee farmer. [volume] (Cheraw S.C.) 1838-1839",
         {"place": "Cheraw", "state": "S.C."}),
        ("Backbone. [volume] (St. Paul, Minn. ;) 1897-1906",
         {"place": "St. Paul", "state": "Minn."}),
        ("Bristol news. [volume] (Bristol, Va. &amp; Tenn.) 1867-189?",
         {"place": "Bristol", "state": "Va. & Tenn.", "last_year": None}),
        # HTML entities, and UTF-8 that was read as Windows-1252
        ("Coeur d&#39;Alene evening press. (Coeur d&#39;Alene, Idaho) 1907-1929",
         {"title": "Coeur d'Alene evening press.", "place": "Coeur d'Alene"}),
        ("Deutscher herold. [volume] (Sioux Falls, SuÌˆd-Dakota) 1907-1918",
         {"state": "Süd-Dakota"}),
        ("The Maryland independent. [volume] (Port Tobacco, Md.) 1874-current",
         {"first_year": 1874, "last_year": None, "years": "1874-current"}),
    ],
)  # fmt: skip
def test_the_hard_cases(paper, fields):
    assert parsed(paper, **fields) == fields


@pytest.mark.parametrize(
    ("printed", "modern"),
    [
        ("Va.", "Virginia"),
        ("W. Va.", "West Virginia"),
        ("Süd-Dakota", "South Dakota"),
        ("Nuevo México", "New Mexico"),
        ("A.T.", "Arizona"),
        ("Minn. Territory", "Minnesota"),
        ("Va. & Tenn.", "Virginia"),
        # a territory's initials can stand for two: the record or the brackets decide
        ("W.T.", None),
        ("N.T.", None),
        ("I.T.", None),
        ("Dakota", None),
    ],
)
def test_a_printed_state_names_its_modern_state_unless_it_could_be_two(printed, modern):
    assert state_name(printed) == modern


def test_then_and_now_says_when_a_place_has_changed_state():
    # 1835: the Virginia free press, of Charlestown, Va., now West Virginia (sn84026784)
    title = parse_title("Virginia free press. (Charlestown, Va. [W. Va.]) 1832-1916")

    assert then_and_now(title, "West Virginia") == "Charlestown, Va. (now W.Va.)"
    assert (
        then_and_now(
            parse_title("Alexandria gazette. [volume] (Alexandria, D.C.) 1834-1974"),
            "Virginia",
        )
        == "Alexandria, D.C. (now Va.)"
    )
    assert (
        then_and_now(
            parse_title("Evening star. [volume] (Washington, D.C.) 1854-1972"),
            "District of Columbia",
        )
        == "Washington, D.C."
    )
    assert (
        then_and_now(
            parse_title(
                "Aberdeen herald. [volume] (Aberdeen, Chehalis County, W.T.) 1886-1917"
            ),
            "Washington",
        )
        == "Aberdeen, W.T. (now Wash.)"
    )
    assert then_and_now(parse_title("The New York herald."), "New York") is None


def test_two_hundred_titles_checked_by_hand():
    cases = json.loads(FIXTURE.read_text())

    assert len({case["paper"] for case in cases}) >= 200
    for case in cases:
        assert parse_title(case["paper"]) == case["expected"], case["paper"]
