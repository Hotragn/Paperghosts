"""Where each paper was printed (decision 34): its printed place geocoded, then checked against
its loc.gov title record where it has one.

1. The printed place is geocoded in its modern state: the cataloguer's bracketed place first,
   then the printed one.
2. With a record that names counties, a result inside one of them stands.
3. A result outside them, or no result at all, gives way to the record's place as catalogued
   today, geocoded in the record's county.
4. Failing that, a ghost town of the record's name in the record's county, flagged historical.
5. Failing that, no point: a pin that disagrees with the record is the dangerous kind of answer.
A record that names no county GeoNames has in its state, as for Alaska's and Connecticut's
places, can't check one: the printed place stands, or where that resolves to nothing, the
record's own place, unchecked. Without a record, the printed place stands unchecked too. That's
so for most papers until 2D asks for the records of the papers it stores (BUILD-PLAN.md).
"""

from paperghosts.geo.titles import state_name


def towns(title):
    found = [t for t in (title.get("supplied_place"), title.get("place")) if t]
    return list(dict.fromkeys(found))


def modern_state(title):
    return title.get("modern_state") or state_name(
        title.get("supplied_state") or title.get("state")
    )


def printed_place(gazetteer, title):
    state, county = modern_state(title), title.get("county")
    found = gazetteer.geocode(None, state)
    for town in towns(title):
        found = gazetteer.geocode(town, state, county)
        if found["place_id"] is not None:
            break
    return found


def paper_place(gazetteer, title, given=None):
    """The GeoNames place a paper was printed in, and what its record (`loc.recorded`) made of
    it, under "record"."""
    printed = printed_place(gazetteer, title)
    if not given or not given.get("place"):
        return printed | {"record": "none"}
    counties = given.get("counties") or []
    agrees = gazetteer.same_county(printed, counties, given["state"])
    if agrees is None:
        why = (
            "can't be checked against GeoNames' counties"
            if counties
            else "has no county to check"
        )
        if printed["place_id"] is not None:
            return printed | {"record": why}
        catalogued = gazetteer.geocode(given["place"], given["state"])
        if catalogued["place_id"] is not None:
            return catalogued | {
                "record": "found what the printed place didn't, unchecked"
            }
        return printed | {"record": why}
    if agrees:
        return printed | {"record": "agrees"}
    how = (
        "replaced the printed place"
        if printed["place_id"] is not None
        else "found what the printed place didn't"
    )
    for county in counties:
        catalogued = gazetteer.geocode(given["place"], given["state"], county)
        if catalogued["place_id"] is not None and gazetteer.same_county(
            catalogued, counties, given["state"]
        ):
            return catalogued | {"record": how}
    ghost = gazetteer.ghost(given["place"], given["state"], counties)
    if ghost:
        return ghost | {"record": "a ghost town in the record's county"}
    return gazetteer.base() | {
        "reason": "outside the record's county, whose own place isn't in GeoNames",
        "record": "disagrees, and its own place isn't in GeoNames",
    }
