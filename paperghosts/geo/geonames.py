"""GeoNames' US dump, and a geocoder over it (decision 34).

`python -m paperghosts.geo.geonames fetch` downloads the dump and the state and county codes
into data/geonames/. It writes manifest.json there with each file's URL, its retrieval date, its
size and sha256, and the CC BY 4.0 licence.

A town and a modern state become a GeoNames ID and a point. Only populated places count
(feature class P). The town is matched by its name or by one of its alternate names. Names are
compared without accents, case, punctuation or spaces ("Charlestown" is "Charles Town"), with
"St." read as Saint. If nothing matches, the name is tried without a leading "The", then
without a trailing "City". Ties break by this rule, in order:
1. a place in the county the title prints, when it prints one
2. a living place, over a section of a place, and over a historical, abandoned or destroyed one
3. a match by name, over a match by alternate name
4. a capital or county seat, over the rest
5. the larger population
6. the lower GeoNames ID
A place that resolves to nothing gets no point, and a reason instead. Every result records
`location_precision: town` and its source.
"""

import hashlib
import json
import re
import shutil
import sys
import unicodedata
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from paperghosts.ingest.crops import USER_AGENT

DIR = Path(__file__).parents[2] / "data" / "geonames"
FILES = {
    "US.zip": "https://download.geonames.org/export/dump/US.zip",
    "admin1CodesASCII.txt": "https://download.geonames.org/export/dump/admin1CodesASCII.txt",
    "admin2Codes.txt": "https://download.geonames.org/export/dump/admin2Codes.txt",
}
LICENCE = {
    "licence": "CC BY 4.0",
    "licence_url": "https://creativecommons.org/licenses/by/4.0/",
    "attribution": "Place data from GeoNames (geonames.org), licensed under CC BY 4.0",
}
SECTION = {"PPLX"}
DEAD = {
    "PPLH",
    "PPLQ",
    "PPLW",
    "PPLCH",
}  # historical, abandoned, destroyed, a former capital
SEATS = {"PPLC", "PPLA", "PPLA2"}
OUTSIDE = {
    "Puerto Rico",
    "Virgin Islands",
    "Guam",
    "American Samoa",
}  # each its own dump
SHORT = {"st": "saint", "ste": "sainte", "ft": "fort", "mt": "mount", "pt": "point"}
COUNTY_WORDS = {"co", "county", "parish", "borough", "census", "area", "municipality"}


def name_key(text):
    """A place name compared without accents, case, punctuation or "St." for Saint."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"['’]", "", text.replace("&", " and "))
    return " ".join(SHORT.get(word, word) for word in re.findall(r"[a-z0-9]+", text))


def flat(key):
    return key.replace(" ", "")


def county_key(text):
    words = name_key(text).split()
    while words and words[-1] in COUNTY_WORDS:
        words.pop()
    return " ".join(words)


def variants(key):
    """The name as given, then without a leading "the", then without a trailing "city"."""
    yield key
    if key.startswith("the "):
        yield key.removeprefix("the ")
    if key.endswith(" city"):
        yield key.removesuffix(" city")


def codes(path):
    with open(path, encoding="utf-8") as rows:
        for row in rows:
            code, name, *_ = row.rstrip("\n").split("\t")
            yield code.split("."), name


class Gazetteer:
    def __init__(self, places=None, admin1=None, admin2=None, source=None):
        places = places or DIR / "US.txt"
        if source is None:
            retrieved = json.loads((DIR / "manifest.json").read_text())["retrieved"]
            source = f"geonames US dump of {retrieved[:10]}"
        self.source = source
        self.states = {
            name: c[1]
            for c, name in codes(admin1 or DIR / "admin1CodesASCII.txt")
            if c[0] == "US"
        }
        self.counties, self.county_names = {}, {}
        for c, name in codes(admin2 or DIR / "admin2Codes.txt"):
            if c[0] == "US":
                self.counties[(c[1], county_key(name))] = c[2]
                self.county_names[(c[1], c[2])] = name
        self.names, self.alternates = defaultdict(list), defaultdict(list)
        with open(places, encoding="utf-8") as rows:
            for row in rows:
                f = row.rstrip("\n").split("\t")
                if f[6] != "P" or f[8] != "US":
                    continue
                place = {
                    "id": int(f[0]),
                    "name": f[1],
                    "lat": float(f[4]),
                    "lon": float(f[5]),
                    "code": f[7],
                    "state": f[10],
                    "county": f[11],
                    "population": int(f[14] or 0),
                }
                keys = {name_key(f[1]), name_key(f[2])} - {""}
                keys |= {k.removeprefix("the ") for k in keys if k.startswith("the ")}
                keys = {flat(k) for k in keys}
                for key in keys:
                    self.names[(key, f[10])].append(place)
                for alternate in f[3].split(","):
                    key = flat(name_key(alternate))
                    if key and key not in keys:
                        self.alternates[(key, f[10])].append(place)

    def geocode(self, town, state, county=None):
        """The GeoNames place for a town in a modern state, or a reason there is none."""
        base = {
            "place_id": None,
            "location_precision": "town",
            "location_source": self.source,
        }
        if not town:
            return base | {"reason": "no town"}
        if not state:
            return base | {"reason": "no state"}
        if state in OUTSIDE:
            return base | {"reason": "outside GeoNames' US dump"}
        code = self.states.get(state)
        if code is None:
            return base | {"reason": f"no state called {state}"}
        for key in variants(name_key(town)):
            found = {}
            for kind, index in (
                ("name", self.names),
                ("alternate name", self.alternates),
            ):
                for place in index.get((flat(key), code), []):
                    found.setdefault(place["id"], (place, kind))
            if found:
                break
        else:
            return base | {"reason": f"no place of that name in {state}"}
        wanted = self.counties.get((code, county_key(county))) if county else None

        def rank(pair):
            place, kind = pair
            alive = 2 if place["code"] in DEAD else 1 if place["code"] in SECTION else 0
            return (
                wanted is not None and place["county"] != wanted,
                alive,
                kind != "name",
                place["code"] not in SEATS,
                -place["population"],
                place["id"],
            )

        place, kind = min(found.values(), key=rank)
        return base | {
            "place_id": place["id"],
            "name": place["name"],
            "state": code,
            "county": self.county_names.get((code, place["county"])),
            "location": {"type": "Point", "coordinates": [place["lon"], place["lat"]]},
            "matched": kind,
            "feature_code": place["code"],
            "population": place["population"],
            "candidates": len(found),
        }


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(directory=DIR):
    """Downloads GeoNames' US dump and its code lists, extracts US.txt, and writes the
    manifest."""
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for name, url in FILES.items():
        path, partial = directory / name, directory / f"{name}.partial"
        headers = {"User-Agent": USER_AGENT}
        with httpx.stream(
            "GET", url, headers=headers, timeout=120, follow_redirects=True
        ) as r:
            r.raise_for_status()
            with open(partial, "wb") as out:
                out.writelines(r.iter_bytes())
            last_modified = r.headers.get("last-modified")
        partial.replace(path)
        files.append(
            {
                "url": url,
                "file": name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "last_modified": last_modified,
            }
        )
    with (
        zipfile.ZipFile(directory / "US.zip") as archive,
        archive.open("US.txt") as dump,
        open(directory / "US.txt", "wb") as out,
    ):
        shutil.copyfileobj(dump, out)
    extracted = directory / "US.txt"
    manifest = {
        "source": "GeoNames",
        **LICENCE,
        "retrieved": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": files,
        "extracted": [
            {
                "file": "US.txt",
                "from": "US.zip",
                "bytes": extracted.stat().st_size,
                "sha256": sha256(extracted),
            }
        ],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        print(json.dumps(fetch(), indent=1))
