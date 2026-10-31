"""The labelling page serves an article's text beside its crops, with RDR-2's fields, and saves
a label only when every quote is in the text, one per article and labeller."""

import json

from fastapi.testclient import TestClient
from label_gold import app

TEXT = (
    "MILFORD, Conn., June 3.-The family of Mr. John Hale have been disturbed every night\n"
    "for a fortnight by knockings upon the walls of the old farmhouse, which no search has\n"
    "been able to explain."
)
ROW = {
    "article_id": "a1",
    "split": "gold",
    "paper": "The Courant",
    "date": "1890-06-05",
    "headline": "A HAUNTED FARMHOUSE",
    "text": TEXT,
    "member": "m",
    "scan": {"raw_data_loc": "r"},
    "bbox_list": [{"x0": 0, "y0": 0, "x1": 10, "y1": 10}],
}
CROP = "0123456789abcdef01234567.jpg"
REPORT = {
    "article_id": "a1",
    "kind": "report",
    "kind_quote": "disturbed every night for a fortnight by knockings",
    "place": {"value": "the old farmhouse", "quote": "the old farmhouse"},
    "place_state": {"value": "Connecticut", "quote": "MILFORD, Conn."},
    "seen": {"value": "knockings upon the walls", "quote": "knockings upon the walls"},
    "outcome": {
        "value": "unexplained",
        "quote": "which no search has\n been able to explain",
    },
    "people": [
        {"value": "the family of Mr. John Hale", "quote": "The family of Mr. John Hale"}
    ],
    "rules": [1],
    "slices": ["E5"],
}


def client(tmp_path, asked):
    (tmp_path / CROP).write_bytes(b"\xff\xd8 a jpeg")

    def crops_for(member, scan, boxes, text=None):
        asked.append((member, len(boxes), text))
        return "service", [tmp_path / CROP]

    out = {"gold": tmp_path / "labels.jsonl", "dev": tmp_path / "dev_labels.jsonl"}
    return TestClient(app({"a1": ROW}, "tester", crops_for, out, tmp_path)), out


def test_it_serves_the_text_beside_its_crops_with_the_fields_and_the_rules(tmp_path):
    asked = []
    web, _ = client(tmp_path, asked)

    page = web.get("/article/a1")

    assert page.status_code == 200
    assert (
        "knockings upon the walls" in page.text and f'src="/crop/{CROP}"' in page.text
    )
    assert asked == [("m", 1, TEXT)]  # through crops_for, which checks the page first
    assert 'data-name="outcome"' in page.text and "inn or hotel" in page.text
    assert 'name="slice" value="E12"' in page.text and 'value="E9"' not in page.text
    # POLICY.md's rule 14, at hand
    assert "Phantom ships, trains and lights" in page.text
    assert web.get(f"/crop/{CROP}").content == b"\xff\xd8 a jpeg"
    assert web.get("/crop/..%2Flabels.jsonl").status_code == 404


def test_it_saves_a_label_whose_quotes_are_in_the_text_and_refuses_one_that_isnt(
    tmp_path,
):
    web, out = client(tmp_path, [])

    refused = web.post(
        "/label", json={**REPORT, "seen": {"value": "a light", "quote": "a light"}}
    )
    assert (
        refused.status_code == 422 and "isn't in the text" in refused.json()["detail"]
    )
    assert not out["gold"].exists()

    assert web.post("/label", json=REPORT).status_code == 200
    assert (
        web.post("/label", json={**REPORT, "note": "checked twice"}).status_code == 200
    )

    (saved,) = [json.loads(line) for line in out["gold"].read_text().splitlines()]
    assert saved["kind"] == "report" and saved["labeller"] == "tester"
    assert (
        saved["outcome"]["value"] == "unexplained" and saved["note"] == "checked twice"
    )
    assert saved["people"] == REPORT["people"] and saved["specific_place"] is None
    assert saved["slices"] == ["E5"]
    assert list(saved)[:3] == ["article_id", "kind", "kind_quote"]


def test_fields_are_for_reports_only_and_choices_come_from_the_schema(tmp_path):
    web, _ = client(tmp_path, [])

    idiom = {**REPORT, "kind": "idiom"}
    assert (
        web.post("/label", json=idiom).json()["detail"] == "fields are for reports only"
    )
    odd = {**REPORT, "outcome": {"value": "spooky", "quote": "the old farmhouse"}}
    assert "not one of" in web.post("/label", json=odd).json()["detail"]
    # E9 comes from the grouping, so a label can't claim it
    reprinted = {**REPORT, "slices": ["E9"]}
    assert "slices" in web.post("/label", json=reprinted).json()["detail"]
