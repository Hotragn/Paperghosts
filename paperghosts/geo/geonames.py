"""GeoNames' dumps for the US, Puerto Rico and the Virgin Islands, and a geocoder over them
(decision 34).

`python -m paperghosts.geo.geonames fetch` downloads the dumps and the state and county codes
into data/geonames/. It writes manifest.json there with each file's URL, its retrieval date, its
size and sha256, and the CC BY 4.0 licence.

A town and a modern state become a GeoNames ID and a point. Puerto Rico and the Virgin Islands
each stand as a state, with their municipios and islands as counties. Only populated places
count (feature class P). The town is matched by its name or by one of its alternate names.
Names are compared without accents, case, punctuation or spaces ("Charlestown" is "Charles
Town"), with "St." read as Saint. If nothing matches, the name is tried without a leading "The",
then without a trailing "City". Ties break by this rule, in order:
1. a place in the county the title prints, when it prints one
2. a living place, over a section of a place, and over a historical, abandoned or destroyed one
3. a match by name, over a match by alternate name
4. a capital or county seat, over the rest
5. the larger population
6. the lower GeoNames ID
A place that resolves to nothing gets no point, and a reason instead. Every result records
`location_precision: town` and its source.

A ghost town that GeoNames files outside populated places, as "Clifton (historical)" in class S,
is found only by `ghost`, which wants a county from the paper's title record.
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
DUMP = "https://download.geonames.org/export/dump"
TERRITORIES = {
    "PR": "Puerto Rico",
    "VI": "Virgin Islands",
}  # each country code, as a state
FILES = {
    "US.zip": f"{DUMP}/US.zip",
    **{f"{code}.zip": f"{DUMP}/{code}.zip" for code in TERRITORIES},
    "admin1CodesASCII.txt": f"{DUMP}/admin1CodesASCII.txt",
    "admin2Codes.txt": f"{DUMP}/admin2Codes.txt",
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
OUTSIDE = {"Guam", "American Samoa"}  # no paper among the candidates is in either
SHORT = {"st": "saint", "ste": "sainte", "ft": "fort", "mt": "mount", "pt": "point"}
# the words around a county's name: "City and Borough of Wrangell", "Nome Census Area"
COUNTY_AFTER = {
    "co",
    "county",
    "parish",
    "borough",
    "census",
    "area",
    "municipality",
    "city",
    "and",
    "independent",
}
COUNTY_BEFORE = {"city", "and", "county", "borough", "of", "town", "municipality"}
HISTORICAL = " (historical)"


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
    while words and words[-1] in COUNTY_AFTER:
        words.pop()
    while words and words[0] in COUNTY_BEFORE:
        words.pop(0)
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
        if places is None:
            places = [DIR / f"{code}.txt" for code in ("US", *TERRITORIES)]
        if source is None:
            retrieved = json.loads((DIR / "manifest.json").read_text())["retrieved"]
            source = f"geonames dumps of {retrieved[:10]}"
        self.source = source
        self.states = {name.lower(): code for code, name in TERRITORIES.items()}
        self.states["u.s. virgin islands"] = "VI"
        self.county_names, self.counties = {}, {}
        for c, name in codes(admin1 or DIR / "admin1CodesASCII.txt"):
            if c[0] == "US":
                self.states[name.lower()] = c[1]
            elif (
                c[0] in TERRITORIES
            ):  # a territory's municipios and islands, as counties
                self.county_names[(c[0], c[1])] = name
        for c, name in codes(admin2 or DIR / "admin2Codes.txt"):
            if c[0] == "US":
                self.county_names[(c[1], c[2])] = name
        for (state, code), name in self.county_names.items():
            self.counties[(state, county_key(name))] = code
        self.names, self.alternates = defaultdict(list), defaultdict(list)
        self.ghosts = defaultdict(list)
        for path in [places] if isinstance(places, str | Path) else places:
            with open(path, encoding="utf-8") as rows:
                for row in rows:
                    self.add(row.rstrip("\n").split("\t"))

    def add(self, f):
        if f[8] == "US":
            state, county = f[10], f[11]
        elif f[8] in TERRITORIES:
            state, county = f[8], f[10]
        else:
            return
        place = {
            "id": int(f[0]),
            "name": f[1],
            "lat": float(f[4]),
            "lon": float(f[5]),
            "code": f[7],
            "state": state,
            "county": county,
            "population": int(f[14] or 0),
        }
        if f[6] == "S" and f[1].endswith(HISTORICAL):
            self.ghosts[(flat(name_key(f[1].removesuffix(HISTORICAL))), state)].append(
                place
            )
            return
        if f[6] != "P":
            return
        keys = {name_key(f[1]), name_key(f[2])} - {""}
        keys |= {k.removeprefix("the ") for k in keys if k.startswith("the ")}
        keys = {flat(k) for k in keys}
        for key in keys:
            self.names[(key, state)].append(place)
        for alternate in f[3].split(","):
            key = flat(name_key(alternate))
            if key and key not in keys:
                self.alternates[(key, state)].append(place)

    def base(self):
        return {
            "place_id": None,
            "location_precision": "town",
            "location_source": self.source,
        }

    def result(self, place):
        return self.base() | {
            "place_id": place["id"],
            "name": place["name"],
            "state": place["state"],
            "county": self.county_names.get((place["state"], place["county"])),
            "location": {"type": "Point", "coordinates": [place["lon"], place["lat"]]},
            "feature_code": place["code"],
            "population": place["population"],
        }

    def geocode(self, town, state, county=None):
        """The GeoNames place for a town in a modern state, or a reason there is none."""
        base = self.base()
        if not town:
            return base | {"reason": "no town"}
        if not state:
            return base | {"reason": "no state"}
        if state in OUTSIDE:
            return base | {"reason": "outside GeoNames' dumps here"}
        code = self.states.get(state.lower())
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
        return self.result(place) | {"matched": kind, "candidates": len(found)}

    def same_county(self, found, counties, state):
        """Whether a result lies in a county a title record names, in the record's state. None
        where that can't be told: for a record that names no county GeoNames has in its state,
        as for Alaska's, which loc.gov names after towns, or Connecticut's, which GeoNames now
        files under planning regions."""
        code = self.states.get((state or "").lower())
        wanted = {county_key(c) for c in counties or []}
        if not any((code, county) in self.counties for county in wanted):
            return None
        return (
            found.get("state") == code
            and county_key(found.get("county") or "") in wanted
        )

    def ghost(self, town, state, counties):
        """A ghost town of that name in a county the record names, flagged historical."""
        code = self.states.get((state or "").lower())
        wanted = {county_key(c) for c in counties or []}
        for place in self.ghosts.get((flat(name_key(town or "")), code), []):
            if county_key(self.county_names.get((code, place["county"]), "")) in wanted:
                return self.result(place) | {
                    "matched": "ghost town",
                    "historical": True,
                }
        return None


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(directory=DIR):
    """Downloads GeoNames' dumps for the US, Puerto Rico and the Virgin Islands and its code
    lists, extracts each country's file, and writes the manifest."""
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
    extracted = []
    for code in ("US", *TERRITORIES):
        target = directory / f"{code}.txt"
        with (
            zipfile.ZipFile(directory / f"{code}.zip") as archive,
            archive.open(f"{code}.txt") as dump,
            open(target, "wb") as out,
        ):
            shutil.copyfileobj(dump, out)
        extracted.append(
            {
                "file": target.name,
                "from": f"{code}.zip",
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
            }
        )
    manifest = {
        "source": "GeoNames",
        **LICENCE,
        "retrieved": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": files,
        "extracted": extracted,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        print(json.dumps(fetch(), indent=1))
