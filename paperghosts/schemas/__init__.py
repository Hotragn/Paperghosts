"""Pydantic models, the single source of truth for every stored record (ARCHITECTURE section 4).
Atlas's validators are generated from them (`paperghosts.store.validators`).

A document is stored as `model_dump(by_alias=True, exclude_none=True)`, so a field with no value
is left out rather than stored as null, and only fields that always have a value are required.
"""

from typing import Annotated, Literal, Self

from bson.binary import VECTOR_SUBTYPE, Binary, BinaryVectorDtype
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainValidator,
    WithJsonSchema,
    model_validator,
)

from paperghosts.ingest import lexicon

DIMENSIONS = 384  # the embedding's (decision 32)

Year = Annotated[int, Field(ge=1770, le=1964)]  # AmericanStories' year files
IsoDate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
Score = Annotated[float, Field(ge=0, le=1)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Count = Annotated[int, Field(ge=0)]
Outcome = Literal["unexplained", "explained", "hoax", "unknown"]
PlaceType = Literal[
    "house", "church", "cemetery", "inn_or_hotel", "road_or_bridge", "public_building",
    "ship", "other",
]  # fmt: skip
Precision = Literal["town", "street", "building"]
LexiconTerm = Literal[*lexicon.GHOST, *lexicon.TOGETHER]


def vector(value: object) -> Binary:
    """An embedding is a BinData vector of float32 or int8 at DIMENSIONS, never an array of
    doubles (decision 32, rule 6)."""
    if not isinstance(value, Binary) or value.subtype != VECTOR_SUBTYPE:
        raise ValueError("an embedding is a BinData vector")
    found = value.as_vector()
    if found.dtype not in (BinaryVectorDtype.FLOAT32, BinaryVectorDtype.INT8):
        raise ValueError("an embedding's vector is float32 or int8")
    if len(found.data) != DIMENSIONS:
        raise ValueError(
            f"an embedding has {DIMENSIONS} dimensions, not {len(found.data)}"
        )
    return value


Vector = Annotated[
    Binary, PlainValidator(vector), WithJsonSchema({"bsonType": "binData"})
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True)


class Versions(Model):
    """What made the record (SRS section 5): the code's git SHA, and whichever of the lexicon,
    model, adapter and prompt versions apply."""

    code: str
    lexicon: str | None = None
    model: str | None = None
    adapter: str | None = None
    prompt: str | None = None


class Point(Model):
    """A GeoJSON point, as a 2dsphere index reads it: longitude first."""

    type: Literal["Point"]
    coordinates: tuple[Longitude, Latitude]


class Box(Model):
    """One box of an article on its page, in the scan's pixels."""

    x0: Count
    y0: Count
    x1: Count
    y1: Count


class Printing(Model):
    """A compact reference to one printing of a story: its paper, its date and where it sits on
    its page. Its crop URLs are derived from service and bbox_list when it is read, not stored,
    and its text isn't kept: the story keeps one printing's (decision 32, rule 6)."""

    article_id: str
    lccn: str
    paper: str
    place: str | None = None  # where it was published, from its title record
    state: str | None = None
    date: IsoDate
    edition: Annotated[int, Field(ge=1)]
    page: Annotated[int, Field(ge=1)]
    service: str | None = None  # its page's IIIF service, once known (decision 29)
    bbox_list: list[Box] = Field(min_length=1)


class Stated(Model):
    """One field the reader reads: its value, the verbatim quote it rests on, whether the
    verifier found that quote in the text, and the reader's score. A field with no verified
    quote is "not stated" and has no value."""

    value: str | None = None
    quote: str | None = None
    verified: bool
    score: Score


class StatedOutcome(Stated):
    value: Outcome | None = None


class StatedPlaceType(Stated):
    value: PlaceType | None = None


class StatedPrecision(Stated):
    value: Precision | None = None


class Fields(Model):
    """The reader's fields (SRS RDR-2). The last three are read for walks."""

    place: Stated
    people: list[Stated]
    seen: Stated
    outcome: StatedOutcome
    specific_place: Stated | None = None
    place_type: StatedPlaceType | None = None
    precision: StatedPrecision | None = None


class Report(Model):
    """One story: its printings, the text of its primary printing as printed, the reader's
    fields, where it happened and its embedding."""

    id: str = Field(alias="_id")
    primary_article_id: str
    printings: list[Printing] = Field(min_length=1)
    headline: str
    text: str
    display_headline: str
    date: IsoDate  # the earliest printing's
    year: Year
    month_day: Annotated[str, Field(pattern=r"^\d{2}-\d{2}$")]
    decade: Annotated[int, Field(ge=1770, le=1960, multiple_of=10)]
    kind: Literal["report"]
    fields: Fields
    location: Point | None = None
    location_precision: Precision | None = None
    location_source: str | None = None
    place_id: Annotated[int, Field(ge=1)] | None = None
    town: str | None = None
    state: str | None = None
    embedding: Vector | None = None
    versions: Versions
    lexicon_terms: list[LexiconTerm] = Field(min_length=1)
    case_id: str | None = None

    @model_validator(mode="after")
    def ids(self) -> Self:
        if self.id != f"r_{self.primary_article_id}":
            raise ValueError("a report's _id is r_ and its primary article ID")
        if self.case_id is not None and self.case_id != f"c_{self.id}":
            raise ValueError("a report's case_id is c_ and its _id")
        return self


class Place(Model):
    """A town, by its GeoNames ID."""

    id: Annotated[int, Field(ge=1)] = Field(alias="_id")
    name: str
    alternate_names: list[str] = []
    state: str
    location: Point
    report_count: Count
    first_year: Year
    last_year: Year
    versions: Versions

    @model_validator(mode="after")
    def years(self) -> Self:
        if self.first_year > self.last_year:
            raise ValueError("a place's first year comes before its last")
        return self


class Clipping(Model):
    article_id: str
    quote: str
    verified: bool


class Claim(Model):
    """A claim is kept only if it cites a clipping whose quote verifies (ARCHITECTURE 3.5)."""

    text: str
    clippings: list[Clipping] = Field(min_length=1)
    confidence: Score


class Followup(Printing):
    relation: Literal[
        "follow_up", "debunking", "arrest", "moved_out", "inquest", "death_notice"
    ]
    quote: str


class Person(Model):
    name: str
    death_notice_article_id: str | None = None
    link_grade: Literal["strong", "possible", "weak"]
    reasons: list[str]


class Now(Model):
    source: str
    url: Annotated[str, Field(pattern=r"^https?://")]
    retrieved: IsoDate
    quote: str


class Difference(Model):
    """A difference between then and now, backed by a quote from each side."""

    text: str
    then_quote: str
    now_quote: str


class ThenNow(Model):
    then: str
    now: list[Now]
    differences: list[Difference]


class Run(Model):
    model: str
    provider: str
    steps: Count
    tokens: Count
    cost_usd: Annotated[float, Field(ge=0)] | None = None
    latency_s: Annotated[float, Field(ge=0)]
    sentry_trace_id: str | None = None
    workflow_id: str


class Case(Model):
    """An investigation of one report."""

    id: str = Field(alias="_id")
    report_id: str
    claims: list[Claim]
    followups: list[Followup]
    person: Person | None = None
    then_now: ThenNow | None = None
    run: Run
    versions: Versions

    @model_validator(mode="after")
    def ids(self) -> Self:
        if self.id != f"c_{self.report_id}":
            raise ValueError("a case's _id is c_ and its report's ID")
        return self


class Outcomes(Model):
    """Stories by outcome, precomputed for the reel so outcome needs no index (decision 32)."""

    unexplained: Count
    explained: Count
    hoax: Count
    unknown: Count


class Stat(Model):
    """One year's or one state's counts, for the reel."""

    id: str = Field(alias="_id")
    scope: Literal["year", "state"]
    year: Year | None = None
    state: str | None = None
    pages: Count
    articles: Count
    candidates: Count
    stories: Count
    printings: Count
    reports_per_million: Annotated[float, Field(ge=0)]
    outcomes: Outcomes
    versions: Versions

    @model_validator(mode="after")
    def scoped(self) -> Self:
        key = self.year if self.scope == "year" else self.state
        if key is None or self.id != f"{self.scope}:{key}":
            raise ValueError("a stat's _id is its scope and that scope's year or state")
        return self
