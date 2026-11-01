"""The API answers in the SRS contract's shapes: health with Atlas up or down, a skeleton
article, and the error format for an article that doesn't exist."""

from fastapi.testclient import TestClient

from api.main import app


class FakeAtlas:
    """Stands in for the paperghosts database: a ping, and one skeleton article."""

    def __init__(self, reachable=True):
        self.skeleton, self.reachable = self, reachable

    async def command(self, name):
        if not self.reachable:
            raise ConnectionError("no route to Atlas")
        return {"ok": 1}

    async def find_one(self, query):
        return {"_id": "a1", "text": "Knockings."} if query == {"_id": "a1"} else None


def test_health_skeleton_and_not_found():
    # not entered with `with`, so the lifespan never reaches Atlas or Sentry
    client = TestClient(app)
    app.state.db = FakeAtlas()

    health = client.get("/api/health").json()
    assert (health["ok"], health["atlas"]) == (True, True) and health["version"]
    assert client.get("/api/skeleton/a1").json() == {"_id": "a1", "text": "Knockings."}
    missing = client.get("/api/skeleton/a2")
    assert missing.status_code == 404
    assert (
        missing.json()["error"]["code"] == "not_found"
        and missing.json()["error"]["message"]
    )

    app.state.db = FakeAtlas(reachable=False)
    assert client.get("/api/health").json()["atlas"] is False


class FakeReports:
    """Stands in for paperghosts.reports: one stored report, and an Atlas Search answer."""

    def __init__(self):
        self.reports, self.pipelines, self.finds = self, [], 0

    async def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        return self

    async def to_list(self):
        return [{"_id": "r_b2", "date": "1850-05-22", "score": 2.5}]

    async def find_one(self, query, fields):
        self.finds += 1
        return (
            {"_id": "r_a1", "headline": "A GHOST.", "text": "Knockings."}
            if query == {"_id": "r_a1"}
            else None
        )


def test_search_and_ghosts_like_this_one():
    client = TestClient(app)
    app.state.db, app.state.liked = (fake := FakeReports()), {}

    found = client.get("/api/search", params={"q": "apparition"}).json()["results"]
    assert found == [{"article_id": "b2", "date": "1850-05-22", "score": 2.5}]
    assert fake.pipelines[0][0]["$search"]["text"]["fuzzy"]["maxEdits"] == 2

    assert client.get("/api/like/a1").json()["results"][0]["article_id"] == "b2"
    assert "moreLikeThis" in fake.pipelines[1][0]["$search"]
    assert client.get("/api/like/a1").status_code == 200
    assert fake.finds == 1  # the report is read from Atlas once, then kept
    assert client.get("/api/like/nope").status_code == 404
    assert client.get("/api/search", params={"q": "a"}).status_code == 422
