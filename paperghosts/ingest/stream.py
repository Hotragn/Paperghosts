"""Streams a faro year file page by page; the tarball never touches the disk."""

import tarfile
from urllib.request import urlopen

import orjson

FARO = (
    "https://huggingface.co/datasets/dell-research-harvard/AmericanStories"
    "/resolve/main/faro_{year}.tar.gz"
)


def pages(url):
    """Yields (member name, page) for each page scan in the faro tarball at url."""
    # urlopen's response is already a file, so tarfile can stream straight from it
    with (
        urlopen(url, timeout=60) as response,
        tarfile.open(fileobj=response, mode="r|gz") as tar,
    ):
        for member in tar:
            if member.isfile():
                yield member.name, orjson.loads(tar.extractfile(member).read())
