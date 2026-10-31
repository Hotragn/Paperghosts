"""Where a paper was printed: its printed place, checked against its loc.gov title record. A
printed place in the record's county stands. One elsewhere, or one that resolves to nothing,
gives way to the record's place. A ghost town is accepted only in the record's county, and
where nothing agrees with the record there is no point at all."""

from collections import Counter

import pytest

from paperghosts.geo import loc
from paperghosts.geo.geonames import Gazetteer
from paperghosts.geo.papers import paper_place

ROWS = [
    (4848880, "Bloomington", "Bloomington", "", 42.0, -93.4, "P", "PPL", "US", "", "IA", "169", "", "", 0),
    (4868404, "Muscatine", "Muscatine", "", 41.424, -91.043, "P", "PPLA2", "US", "", "IA", "139", "", "", 23000),
    (5007989, "Saginaw", "Saginaw", "", 43.419, -83.951, "P", "PPLA2", "US", "", "MI", "145", "", "", 48000),
    (5763634, "Clifton (historical)", "Clifton (historical)", "", 44.6, -100.0, "S", "", "US", "", "SD", "119", "", "", 0),
    (4801850, "Charles Town", "Charles Town", "", 39.289, -77.86, "P", "PPLA2", "US", "", "WV", "037", "", "", 5899),
    (5500000, "Lardo", "Lardo", "", 40.0, -100.0, "P", "PPL", "US", "", "NE", "001", "", "", 10),
    (5873776, "Seward", "Seward", "", 60.104, -149.442, "P", "PPL", "US", "", "AK", "122", "", "", 2717),
]  # fmt: skip
ADMIN1 = "US.IA\tIowa\nUS.MI\tMichigan\nUS.SD\tSouth Dakota\nUS.WV\tWest Virginia\nUS.ID\tIdaho\nUS.NE\tNebraska\nUS.AK\tAlaska\n"
ADMIN2 = "US.IA.169\tStory County\nUS.IA.139\tMuscatine County\nUS.MI.145\tSaginaw County\nUS.SD.119\tSully County\nUS.WV.037\tJefferson County\nUS.NE.001\tAdams County\nUS.ID.085\tValley County\nUS.AK.122\tKenai Peninsula Borough\n"


@pytest.fixture
def gazetteer(tmp_path):
    places = tmp_path / "US.txt"
    places.write_text(
        "".join(
            "\t".join(map(str, (*r, "", "", "America/Chicago", "2026-10-30"))) + "\n"
            for r in ROWS
        )
    )
    admin1 = tmp_path / "admin1CodesASCII.txt"
    admin1.write_text("".join(f"{line}\tx\t1\n" for line in ADMIN1.splitlines()))
    admin2 = tmp_path / "admin2Codes.txt"
    admin2.write_text("".join(f"{line}\tx\t1\n" for line in ADMIN2.splitlines()))
    return Gazetteer([places], admin1, admin2, source="geonames dumps of 2026-10-30")


def title(place, state, modern):
    return {"place": place, "state": state, "modern_state": modern}


def record(place, county, state, counties=None, states=None):
    counties = counties or ([county] if county else [])
    return {
        "place": place,
        "state": state,
        "counties": counties,
        "states": states or [state],
    }


def test_a_printed_place_in_its_records_county_stands(gazetteer):
    found = paper_place(
        gazetteer,
        title("Charlestown", "Va.", "West Virginia"),
        record("Charles Town", "jefferson", "West Virginia"),
    )

    assert found["place_id"] == 4801850 and found["record"] == "agrees"


def test_a_paper_that_moved_across_a_state_line_is_checked_against_both(gazetteer):
    # Zajedničar (Allegheny, Pa.): its record's place is Youngstown, Ohio, where it moved later
    moved = record(
        "Muscatine",
        "muscatine",
        "Iowa",
        ["jefferson", "muscatine"],
        ["West Virginia", "Iowa"],
    )
    found = paper_place(gazetteer, title("Charlestown", "Va.", "West Virginia"), moved)

    assert found["place_id"] == 4801850 and found["record"] == "agrees"


def test_a_printed_place_in_another_county_gives_way_to_the_records(gazetteer):
    # Muscatine journal (Bloomington, Iowa): Bloomington was Muscatine's name until 1849
    found = paper_place(
        gazetteer,
        title("Bloomington", "Iowa", "Iowa"),
        record("Muscatine", "muscatine", "Iowa"),
    )

    assert (
        found["place_id"] == 4868404 and found["record"] == "replaced the printed place"
    )


def test_a_merged_town_is_found_under_its_successor(gazetteer):
    found = paper_place(
        gazetteer,
        title("East Saginaw", "Mich.", "Michigan"),
        record("Saginaw", "saginaw", "Michigan"),
    )

    assert (
        found["place_id"] == 5007989
        and found["record"] == "found what the printed place didn't"
    )


def test_a_ghost_town_is_taken_only_in_its_records_county(gazetteer):
    found = paper_place(
        gazetteer,
        title("Clifton", "Dakota", "South Dakota"),
        record("Clifton", "sully", "South Dakota"),
    )

    assert found["place_id"] == 5763634 and found["historical"] is True
    assert found["record"] == "a ghost town in the record's county"


def test_with_nothing_that_agrees_with_the_record_there_is_no_point(gazetteer):
    # a same-named place elsewhere is the dangerous kind of answer
    found = paper_place(
        gazetteer,
        title("Lardo", "Idaho", "Nebraska"),
        record("McCall", "valley", "Idaho"),
    )

    assert found["place_id"] is None
    assert found["record"] == "disagrees, and its own place isn't in GeoNames"


def test_a_county_geonames_doesnt_have_leaves_the_printed_place_unchecked(gazetteer):
    # loc.gov files Seward, Alaska, under "Seward"; GeoNames, under the Kenai Peninsula Borough
    found = paper_place(
        gazetteer,
        title("Seward", "Alaska", "Alaska"),
        record("Seward", "seward", "Alaska"),
    )

    assert found["place_id"] == 5873776
    assert found["record"] == "can't be checked against GeoNames' counties"
    # and where the printed place resolves to nothing, the record's place is taken unchecked
    renamed = paper_place(
        gazetteer,
        title("Resurrection Bay", "Alaska", "Alaska"),
        record("Seward", "seward", "Alaska"),
    )
    assert renamed["place_id"] == 5873776
    assert renamed["record"] == "found what the printed place didn't, unchecked"


def test_without_a_record_or_its_county_the_printed_place_stands(gazetteer):
    printed = title("Bloomington", "Iowa", "Iowa")

    assert paper_place(gazetteer, printed, None)["record"] == "none"
    unchecked = paper_place(gazetteer, printed, record("Bloomington", None, "Iowa"))
    assert (
        unchecked["place_id"] == 4848880
        and unchecked["record"] == "has no county to check"
    )


def test_the_lookup_names_the_records_town_only_where_the_point_is_the_records(
    gazetteer, tmp_path, monkeypatch
):
    import titles  # scripts/titles.py

    def record_of(**location):
        return {
            "url": "https://www.loc.gov/item/x/?fo=json",
            "retrieved": "2026-10-30T12:00:00+00:00",
            "status": 200,
            "body": {"item": location},
        }

    records = {
        # renamed: Bloomington was Muscatine's name until 1849
        "sn88059754": record_of(
            location_str="Muscatine, Iowa",
            location_county=["muscatine"],
            location_state=["iowa"],
        ),
        # moved: like Zajedničar's, the record names where the paper went later, so the printed town stands
        "sn84024547": record_of(
            location_str="Muscatine, Iowa",
            location_county=["jefferson", "muscatine"],
            location_state=["west virginia", "iowa"],
        ),
    }
    for lccn in records:
        (tmp_path / f"{lccn}.json").write_text("{}")
    asked = []
    monkeypatch.setattr(loc, "CACHE", tmp_path)
    monkeypatch.setattr(
        loc,
        "title_record",
        lambda lccn, cache=None: asked.append(lccn) or records[lccn],
    )

    renamed = titles.entry(
        "sn88059754",
        Counter({"Muscatine journal. [volume] (Bloomington, Iowa) 1849-185?": 2}),
        Counter({"Iowa": 2}),
        gazetteer,
    )
    moved = titles.entry(
        "sn84024547",
        Counter({"Virginia free press. (Charlestown, Va. [W. Va.]) 1832-1916": 1}),
        Counter({"West Virginia": 1}),
        gazetteer,
    )
    uncached = titles.entry(
        "sn84038114",
        Counter({"Iowa state gazette. (Burlington, Iowa) 1847-1848": 1}),
        Counter({"Iowa": 1}),
        gazetteer,
    )

    assert renamed["then_and_now"] == "Bloomington, Iowa (now Muscatine)"
    assert (
        renamed["catalogued_place"] == "Muscatine"
        and renamed["catalogued_county"] == "Muscatine"
    )
    assert (
        moved["then_and_now"] == "Charlestown, Va. (now W.Va.)"
        and moved["catalogued_place"] == "Muscatine"
    )
    # a record is asked for only where it's cached, for a paper whose title string names its place
    assert asked == ["sn88059754", "sn84024547"] and "catalogued_place" not in uncached
