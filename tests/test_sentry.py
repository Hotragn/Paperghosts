"""Sentry stays off without a DSN, and its events carry no query strings, coordinates,
local variables or host name."""

import random
import socket
import uuid

import pytest
import sentry_sdk
from sentry_sdk.client import NonRecordingClient

from paperghosts import config
from paperghosts.observability.sentry import init_sentry


@pytest.fixture
def clean_sentry(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "missing")
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    yield
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)


def test_off_without_a_dsn(clean_sentry):
    assert init_sentry("pipeline") is False
    assert isinstance(sentry_sdk.get_client(), NonRecordingClient)


def test_events_carry_no_query_strings_coordinates_locals_or_host(
    clean_sentry, monkeypatch
):
    monkeypatch.setenv(
        "SENTRY_DSN", "https://" + "0" * 32 + "@o1.ingest.us.sentry.io/1"
    )
    assert init_sentry("pipeline") is True
    sent = []
    monkeypatch.setattr(
        sentry_sdk.get_client().transport, "capture_envelope", sent.append
    )
    # made at run time: Sentry ships source lines, so literals here would show up anyway
    key, lat, lon = uuid.uuid4().hex, random.uniform(25, 49), random.uniform(-124, -67)

    sentry_sdk.add_breadcrumb(
        category="httpx",
        data={
            "url": f"https://serpapi.com/search?api_key={key}",
            "http.query": f"api_key={key}",
        },
    )

    def near(lat, lon):
        uri = f"mongodb+srv://u:{key}@h/"  # noqa: F841  a local that must not ship
        raise RuntimeError(f"no reports near /api/near?lat={lat}&lon={lon}")

    try:
        near(lat, lon)
    except RuntimeError:
        sentry_sdk.capture_exception()

    body = b"".join(envelope.serialize() for envelope in sent).decode()
    assert "no reports near /api/near" in body
    for private in (key, str(lat), str(lon), socket.gethostname()):
        assert private not in body
