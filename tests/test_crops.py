"""Crop URLs name the scan's IIIF service from its batch path, and one crop covers every
box of an article in the scan's own pixels."""

from paperghosts.ingest.crops import crop_url, service_id

# the Litchfield enquirer, 1850-04-25, as AmericanStories records its scan
RAW_DATA_LOC = (
    "https://chroniclingamerica.loc.gov/data/batches/ct_barnum_ver01/data/sn84020071"
    "/00414182975/1850042501/0199.jp2"
)
SERVICE = (
    "service:ndnp:ct:batch_ct_barnum_ver01:data:sn84020071:00414182975:1850042501:0199"
)


def test_service_id_comes_from_the_batch_path():
    assert service_id(RAW_DATA_LOC) == SERVICE


def test_one_crop_covers_every_box():
    # the Lewistown gazette's 1850-07-26 knockings: masthead line, headline, then the body
    boxes = [
        {"x0": 4886, "y0": 1300, "x1": 5818, "y1": 1398},
        {"x0": 5039, "y0": 1467, "x1": 5735, "y1": 1530},
        {"x0": 4913, "y0": 1543, "x1": 5867, "y1": 4903},
    ]
    assert crop_url(SERVICE, boxes) == (
        f"https://tile.loc.gov/image-services/iiif/{SERVICE}/4886,1300,981,3603/pct:50/0/default.jpg"
    )
