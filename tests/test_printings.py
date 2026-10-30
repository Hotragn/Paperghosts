"""A printing's reference, built from its candidate row: its place in the archive from its
member name, its LCCN from there when the record has none, its page from the scan record only,
and its IIIF service only from the scan's batch path, whose frame wins over the member's."""

from paperghosts.store.printings import printing, scan_number

# as in decision 33: the member's frame is one more than the batch path's jp2
MEMBER = "faro_1910/1910-02-10_p3_sn82016187_100493962_1910021001_0164.json"
RAW = (
    "https://chroniclingamerica.loc.gov/data/batches/mnhi_example_ver01/data/sn82016187"
    "/100493962/1910021001/0163.jp2"
)


def row(**changes):
    return {
        "member": MEMBER,
        "article_id": "4_1910-02-10_p3_sn82016187_100493962_1910021001_0164.json",
        "lccn": "sn82016187",
        "paper": "The Bemidji daily pioneer.",
        "state": "Minnesota",
        "date": "1910-02-10",
        "scan": {"edition": "ed-01", "page": "3", "raw_data_loc": RAW},
        "bbox_list": [{"x0": 10, "y0": 20, "x1": 300, "y1": 400}],
    } | changes


def test_a_printing_is_located_by_its_member_and_its_service_by_its_batch_path():
    found = printing(row())

    assert (found["edition"], found["reel"], found["issue"], found["frame"]) == (
        1,
        "100493962",
        "1910021001",
        "0164",
    )
    assert found["page"] == 3
    assert found["service"].endswith(":sn82016187:100493962:1910021001:0163")


def test_without_a_batch_path_a_printing_has_no_service_until_its_page_is_checked():
    found = printing(row(scan={"edition": None, "page": "na"}))

    assert "service" not in found and "page" not in found
    assert found["frame"] == "0164"


def test_a_missing_lccn_comes_from_the_member_but_the_page_never_does():
    found = printing(row(lccn=None, paper=None, scan=None))

    assert found["lccn"] == "sn82016187" and "paper" not in found
    assert "page" not in found  # not the member's p3


def test_a_scan_records_page_is_a_number_only_when_it_is_one():
    found = [scan_number(v) for v in ("8", "na", None, "", "0")]

    assert found == [8, None, None, None, None]
