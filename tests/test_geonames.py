"""The GeoNames geocoder, on a small dump in GeoNames' own format: a town and state become a
GeoNames ID and a point by its name or an alternate name, and ties break by the written rule.
Historical places count when nothing living matches. An unresolved place gets no point, and a
reason."""

import pytest

from paperghosts.geo.geonames import Gazetteer

# geonameid, name, asciiname, alternatenames, lat, lon, class, code, country, cc2,
# admin1, admin2, admin3, admin4, population, elevation, dem, timezone, modified
ROWS = [
    (4801859, "Charles Town", "Charles Town", "", 39.289, -77.86, "P", "PPLA2", "US", "", "WV", "037", "", "", 5900),
    (4801860, "Charlestown", "Charlestown", "", 39.2, -77.9, "P", "PPLH", "US", "", "WV", "037", "", "", 0),
    # the capital, which lists Charlestown among its alternate names
    (4801848, "Charleston", "Charleston", "Charlestown", 38.35, -81.633, "P", "PPLA", "US", "", "WV", "039", "", "", 46838),
    (5037649, "Saint Paul", "Saint Paul", "St. Paul", 44.944, -93.093, "P", "PPLA", "US", "", "MN", "123", "", "", 285000),
    (4140963, "Washington", "Washington", "Washington D.C.", 38.895, -77.036, "P", "PPLC", "US", "", "DC", "001", "", "", 689000),
    (5740900, "The Dalles", "The Dalles", "Dalles,Dalles City", 45.594, -121.178, "P", "PPLA2", "US", "", "OR", "065", "", "", 15000),
    # two Washingtons in Pennsylvania: the county seat wins unless the title names a county
    (5218069, "Washington", "Washington", "", 40.174, -80.246, "P", "PPLA2", "US", "", "PA", "125", "", "", 13000),
    (5218070, "Washington", "Washington", "", 41.0, -76.0, "P", "PPL", "US", "", "PA", "037", "", "", 200),
    # a living place beside a historical one of the same name
    (4889000, "Juliet", "Juliet", "", 41.0, -88.0, "P", "PPLH", "US", "", "IL", "197", "", "", 0),
    (4889001, "DeKalb", "DeKalb", "", 41.93, -88.75, "P", "PPLA2", "US", "", "IL", "037", "", "", 43000),
    (4893171, "Joliet", "Joliet", "Juliet", 41.525, -88.081, "P", "PPLA2", "US", "", "IL", "197", "", "", 150000),
    # only historical
    (5520000, "Bannock City", "Bannock City", "", 43.8, -115.8, "P", "PPLH", "US", "", "ID", "015", "", "", 0),
    (5000000, "Not a town", "Not a town", "", 1.0, 1.0, "H", "LK", "US", "", "MN", "", "", "", 0),
]  # fmt: skip
ADMIN1 = [
    ("US.WV", "West Virginia"),
    ("US.MN", "Minnesota"),
    ("US.DC", "District of Columbia"),
    ("US.OR", "Oregon"),
    ("US.PA", "Pennsylvania"),
    ("US.IL", "Illinois"),
    ("US.ID", "Idaho"),
]
ADMIN2 = [("US.WV.037", "Jefferson County"), ("US.PA.125", "Washington County"), ("US.PA.037", "Columbia County"), ("US.IL.197", "Will County")]  # fmt: skip


@pytest.fixture
def gazetteer(tmp_path):
    places = tmp_path / "US.txt"
    places.write_text(
        "".join(
            "\t".join(map(str, (*row, "", "", "America/New_York", "2026-10-30"))) + "\n"
            for row in ROWS
        )
    )
    admin1 = tmp_path / "admin1CodesASCII.txt"
    admin1.write_text("".join(f"{code}\t{name}\t{name}\t1\n" for code, name in ADMIN1))
    admin2 = tmp_path / "admin2Codes.txt"
    admin2.write_text("".join(f"{code}\t{name}\t{name}\t1\n" for code, name in ADMIN2))
    return Gazetteer(places, admin1, admin2, source="geonames US dump of 2026-10-30")


def test_a_town_and_state_become_a_geonames_id_and_a_point(gazetteer):
    found = gazetteer.geocode("St. Paul", "Minnesota")

    assert found["place_id"] == 5037649 and found["matched"] == "name"
    assert found["location"] == {"type": "Point", "coordinates": [-93.093, 44.944]}
    assert found["location_precision"] == "town"
    assert found["location_source"] == "geonames US dump of 2026-10-30"


@pytest.mark.parametrize(
    ("town", "state", "county", "place_id", "matched"),
    [
        # Charlestown, Va., now Charles Town, W.Va.: names compare without their spaces, so
        # it isn't the capital that lists Charlestown, nor the dead Charlestown
        ("Charlestown", "West Virginia", None, 4801859, "name"),
        ("De Kalb", "Illinois", None, 4889001, "name"),
        ("Washington City", "District of Columbia", None, 4140963, "name"),
        ("Dalles", "Oregon", None, 5740900, "name"),
        ("Washington", "Pennsylvania", None, 5218069, "name"),
        ("Washington", "Pennsylvania", "Columbia Co.", 5218070, "name"),
        ("Juliet", "Illinois", None, 4893171, "alternate name"),
        ("Bannock City", "Idaho", None, 5520000, "name"),
    ],
)
def test_ties_break_by_the_written_rule(
    gazetteer, town, state, county, place_id, matched
):
    found = gazetteer.geocode(town, state, county)

    assert (found["place_id"], found["matched"]) == (place_id, matched)


@pytest.mark.parametrize(
    ("town", "state", "reason"),
    [
        (None, "Minnesota", "no town"),
        ("Saint Paul", None, "no state"),
        ("San Juan", "Puerto Rico", "outside GeoNames' US dump"),
        ("Not a town", "Minnesota", "no place of that name in Minnesota"),
    ],
)
def test_an_unresolved_place_gets_no_point_and_a_reason(gazetteer, town, state, reason):
    found = gazetteer.geocode(town, state)

    assert found["place_id"] is None and "location" not in found
    assert found["reason"] == reason
    assert found["location_precision"] == "town" and found["location_source"]
