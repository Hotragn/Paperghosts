"""A dropped request to the local server is asked again, and gives up after its last try."""

import httpx
import local_teacher
import pytest


def test_a_dropped_request_is_asked_again(monkeypatch):
    calls = []

    def flaky(*args):
        calls.append(args)
        if len(calls) == 1:
            raise httpx.RemoteProtocolError("Server disconnected")
        return {"article_id": "a"}

    monkeypatch.setattr(local_teacher, "one", flaky)
    monkeypatch.setattr(local_teacher.time, "sleep", lambda s: None)
    assert local_teacher.patient({}, "m", "s", False) == {"article_id": "a"}
    assert len(calls) == 2


def test_it_gives_up_after_its_last_try(monkeypatch):
    def down(*args):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(local_teacher, "one", down)
    monkeypatch.setattr(local_teacher.time, "sleep", lambda s: None)
    with pytest.raises(httpx.ConnectError):
        local_teacher.patient({}, "m", "s", False, tries=2)
