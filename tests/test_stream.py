"""The page reader streams a faro tarball page by page from a URL, skipping directories,
and reports its progress: pages done and compressed bytes read."""

import io
import tarfile

import orjson

from paperghosts.ingest.stream import pages


def test_pages_stream_from_a_url(tmp_path):
    path = tmp_path / "faro_1850.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        folder = tarfile.TarInfo("faro_1850")
        folder.type = tarfile.DIRTYPE
        tar.addfile(folder)
        for i in range(2):
            data = orjson.dumps({"full articles": [{"id": f"a{i}"}]})
            info = tarfile.TarInfo(f"faro_1850/page_{i}.json")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

    progress = []
    streamed = [
        (name, page["full articles"][0]["id"])
        for name, page in pages(path.as_uri(), lambda *done: progress.append(done))
    ]
    assert streamed == [
        ("faro_1850/page_0.json", "a0"),
        ("faro_1850/page_1.json", "a1"),
    ]
    assert [members for members, _ in progress] == [1, 2]
    assert 0 < progress[-1][1] <= path.stat().st_size
