"""The Morgue's Atlas Search pipelines over paperghosts.reports, through the reports_search index:
fuzzy, so a word the OCR misread still finds its report, and moreLikeThis for ghosts like this
one. Shared by the API and scripts/query_demo_atlas.py."""

PATHS = [
    "headline",
    "text",
    "fields.place.value",
    "fields.seen.value",
    "fields.specific_place.value",
]
SHOWN = {
    "_id": 1,
    "date": 1,
    "display_headline": 1,
    "paper": {"$first": "$printings.paper"},
    "place": "$fields.place.value",
    "score": {"$meta": "searchScore"},
    "highlights": {"$meta": "searchHighlights"},
}


def fuzzy(words: str) -> list:
    return [
        {
            "$search": {
                "index": "reports_search",
                "text": {
                    "query": words,
                    "path": PATHS,
                    "fuzzy": {"maxEdits": 2, "prefixLength": 1},
                },
                "highlight": {"path": ["headline", "text"]},
            }
        },
        {"$limit": 5},
        {"$project": SHOWN},
    ]


def like(doc: dict) -> list:
    return [
        {
            "$search": {
                "index": "reports_search",
                "moreLikeThis": {
                    "like": {"headline": doc["headline"], "text": doc["text"][:2000]}
                },
            }
        },
        {"$match": {"_id": {"$ne": doc["_id"]}}},
        {"$limit": 5},
        {"$project": {k: v for k, v in SHOWN.items() if k != "highlights"}},
    ]
