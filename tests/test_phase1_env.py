"""The faro reader counts pages and articles and keeps the Stratford knockings, even when
the stream arrives in small chunks."""

import io
import queue
import tarfile

import orjson
import phase1_env


def page(number, *texts):
    return {
        "lccn": {
            "title": "The test herald. (Stratford, Conn.) 1850-1851",
            "lccn": "sn0",
        },
        "edition": {"date": "1850-04-12"},
        "scan": {
            "width": 10,
            "height": 10,
            "raw_data_loc": "https://example.org/1.jp2",
        },
        "full articles": [
            {
                "id": f"p{number}a{i}",
                "headline": "",
                "article": text,
                "bbox": [0, 0, 1, 1],
            }
            for i, text in enumerate(texts)
        ],
    }


def tarball(pages):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for i, content in enumerate(pages):
            data = orjson.dumps(content)
            info = tarfile.TarInfo(f"faro_1850/page_{i}.json")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_reader_counts_and_keeps_the_stratford_knockings():
    data = tarball(
        [
            page(0, "A Stratford man was knocked down by a horse.", "Wheat is up."),
            page(
                1,
                "Ships arrived.",
                "Knockings at Dr. Phelps's house in Stratford.",
                "Fair.",
            ),
        ]
    )
    chunks = queue.SimpleQueue()
    for i in range(0, len(data), 100):  # small chunks, so reads cross chunk boundaries
        chunks.put(data[i : i + 100])
    chunks.put({"bytes": len(data), "seconds": 1.0})

    stream = phase1_env.Chunks(chunks)
    pages, articles, matches = phase1_env.read_pages(io.BufferedReader(stream))

    assert (pages, articles) == (2, 5)
    assert [m["article"]["id"] for m in matches] == ["p1a1", "p0a0"]  # Phelps first
    assert matches[0]["page"]["edition"] == {"date": "1850-04-12"}
    assert stream.finish() == {"bytes": len(data), "seconds": 1.0}
