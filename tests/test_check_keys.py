"""make keys must never show a value, whole or as any 6-character slice."""

import random
import string

import check_keys
import httpx
import pymongo
import pytest

from paperghosts import config

rng = random.Random(1850)


def rand(n, chars=string.ascii_letters + string.digits):
    return "".join(rng.choices(chars, k=n))


def hexes(n):
    return rand(n, "0123456789abcdef")


def digits(n):
    return rand(n, string.digits)


# shaped like the real values, so each check runs as far as its call
CANARIES = {
    "TINKER_API_KEY": "tml-" + rand(60),
    "MONGODB_URI": f"mongodb+srv://{rand(8)}:{rand(20)}@{hexes(12)}.example.net/?appName={rand(8)}",
    "RENDER_API_KEY": "rnd_" + rand(28),
    "SENTRY_DSN": f"https://{hexes(32)}@o{digits(7)}.ingest.us.sentry.io/{digits(7)}",
    "SENTRY_DSN_WEB": f"https://{hexes(32)}@o{digits(7)}.ingest.us.sentry.io/{digits(7)}",
    "SENTRY_AUTH_TOKEN": "sntryu_" + hexes(64),
    "SENTRY_ORG": hexes(8),
    "SENTRY_PROJECT": hexes(15),
    "SERPAPI_API_KEY": hexes(64),
    "PAPERINSTRUMENTS_API_KEY": rand(46),
    "ULTRAMARINE_BASE_URL": f"https://{hexes(10)}.example.com/v1",
    "ULTRAMARINE_MODEL": hexes(19),
    "HF_TOKEN": "hf_" + rand(34),
    "GEMINI_API_KEY": rand(53),
    "ELEVENLABS_API_KEY": rand(51),
    "TABPFN_TOKEN": rand(53),
}


def echo(*args, **kwargs):
    # what a careless library error or a hostile server quotes back: everything it was given
    return f"{args} {kwargs}"


@pytest.mark.parametrize("mode", ["raise", "reject", "accept"])
def test_make_keys_never_shows_a_value(mode, tmp_path, monkeypatch, capfd):
    env = tmp_path / ".env"
    env.write_text("".join(f"{name}={value}\n" for name, value in CANARIES.items()))
    monkeypatch.setattr(config, "ENV_FILE", env)
    for name in {*CANARIES, *check_keys.KEYS}:
        monkeypatch.delenv(name, raising=False)

    def get(url, **kwargs):
        if mode == "raise":
            raise httpx.ConnectError(echo(url, **kwargs))
        if mode == "reject":
            return httpx.Response(401, text=echo(url, **kwargs))
        # real bodies carry account details too; SerpApi's even repeats the key
        said = echo(url, **kwargs)
        return httpx.Response(
            200, json={"total_searches_left": 250, "data": [said], "api_key": said}
        )

    class Mongo:
        def __init__(self, uri, **kwargs):
            if mode == "raise":
                raise pymongo.errors.ConfigurationError(echo(uri, **kwargs))
            self.admin, self.uri = self, uri

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def command(self, name):
            if mode == "reject":
                raise pymongo.errors.OperationFailure(echo(self.uri, name))
            return {
                "authInfo": {
                    "authenticatedUsers": [{"user": echo(self.uri), "db": "admin"}]
                }
            }

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(pymongo, "MongoClient", Mongo)

    try:
        code, crash = check_keys.main(), ""
    except Exception as exc:  # noqa: BLE001  a crash must not quote a value either
        code, crash = None, repr(exc)
    out, err = capfd.readouterr()
    shown = (
        out
        + err
        + crash
        + "".join(f"{s!r} {s}" for s in map(config.setting, check_keys.KEYS))
    )

    leaked = [
        n
        for n, v in CANARIES.items()
        if any(v[i : i + 6] in shown for i in range(len(v) - 5))
    ]
    assert leaked == []
    assert code == (0 if mode == "accept" else 1)
