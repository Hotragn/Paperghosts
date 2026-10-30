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
