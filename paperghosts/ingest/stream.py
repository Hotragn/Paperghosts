"""Streams a faro year file page by page; the tarball never touches the disk."""

import tarfile
from urllib.request import urlopen

import orjson

FARO = (
    "https://huggingface.co/datasets/dell-research-harvard/AmericanStories"
    "/resolve/main/faro_{year}.tar.gz"
)


class Counted:
    """A file whose reads are counted, so progress can report the bytes streamed so far."""

    def __init__(self, raw):
        self.raw, self.bytes_read = raw, 0

    def read(self, size=-1):
        data = self.raw.read(size)
        self.bytes_read += len(data)
        return data


def pages(url, progress=None):
    """Yields (member name, page) for each page scan in the faro tarball at url. If given,
    progress(pages_done, bytes_read) is called after each page."""
    # urlopen's response is already a file, so tarfile can stream straight from it
    with urlopen(url, timeout=60) as response:
        counted = Counted(response)
        with tarfile.open(fileobj=counted, mode="r|gz") as tar:
            done = 0
            for member in tar:
                if member.isfile():
                    yield member.name, orjson.loads(tar.extractfile(member).read())
                    done += 1
                    if progress:
                        progress(done, counted.bytes_read)
