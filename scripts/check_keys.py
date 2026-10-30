"""make keys: a shape check, then one cheap authenticated call, for each key the build uses.

Prints each name with OK, FAIL or EMPTY and a reason, never a value. Exits 1 if a check
fails or a required key is empty. Unused keys are only reported as present or empty.
"""

import re
import sys
from urllib.parse import urlsplit

import httpx
import pymongo

from paperghosts.config import setting

REQUIRED, OPTIONAL, UNUSED = "required", "optional", "unused"
TINKER = "https://tinker.thinkingmachines.dev/services/tinker-prod"


class Failed(Exception):
    """A failure told with fixed text and status codes only, so it is safe to print."""


def get(url, **kwargs):
    response = httpx.get(url, timeout=10, **kwargs)
    if response.status_code != 200:
        raise Failed(f"HTTP {response.status_code}")
    return response.json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def matches(pattern):
    return lambda value: re.fullmatch(pattern, value) is not None


def mongo_uri(value):
    url = urlsplit(value)
    has_login = bool(url.username and url.password and url.hostname)
    return url.scheme in ("mongodb", "mongodb+srv") and has_login


def sentry_dsn(value):
    url = urlsplit(value)
    return (
        url.scheme == "https"
        and re.fullmatch("[0-9a-f]{32}", url.username or "") is not None
        and (url.hostname or "").endswith(".sentry.io")
        and url.path.strip("/").isdigit()
    )


def https_url(value):
    url = urlsplit(value)
    return url.scheme == "https" and bool(url.hostname)


def tinker(key):
    # the route `tinker auth login` checks keys with; no SDK import, no session
    get(f"{TINKER}/api/v1/auth/apikey/me", headers={"X-API-Key": key})
    return "key accepted"


def atlas(uri):
    with pymongo.MongoClient(uri, serverSelectionTimeoutMS=10_000) as client:
        status = client.admin.command("connectionStatus")
    if not status["authInfo"]["authenticatedUsers"]:
        raise Failed("connected, but not authenticated")
    return "authenticated"


def render(key):
    get("https://api.render.com/v1/owners", params={"limit": 1}, headers=bearer(key))
    return "key accepted"


def sentry(token):
    org, project = setting("SENTRY_ORG").get(), setting("SENTRY_PROJECT").get()
    get(f"https://sentry.io/api/0/projects/{org}/{project}/", headers=bearer(token))
    return "project readable"


def serpapi(key):
    # the account endpoint uses no searches
    account = get("https://serpapi.com/account.json", params={"api_key": key})
    return f"{int(account['total_searches_left'])} searches left"


def ultramarine(key):
    base = setting("ULTRAMARINE_BASE_URL").get().rstrip("/")
    if not base:
        raise Failed("ULTRAMARINE_BASE_URL is empty")
    models = get(f"{base}/models", headers=bearer(key))
    return f"models listed: {len(models['data'])}"


def huggingface(token):
    get("https://huggingface.co/api/whoami-v2", headers=bearer(token))
    return "token accepted"


SLUG = r"[a-z0-9][a-z0-9_-]*"

# name: (need, shape, cheap authenticated call)
KEYS = {
    "TINKER_API_KEY": (REQUIRED, matches(r"tml-[\w-]{20,}"), tinker),
    "MONGODB_URI": (REQUIRED, mongo_uri, atlas),
    "RENDER_API_KEY": (REQUIRED, matches(r"rnd_[A-Za-z0-9]{20,}"), render),
    # a DSN can only prove itself by sending an event, which phase1_env does
    "SENTRY_DSN": (REQUIRED, sentry_dsn, None),
    "SENTRY_DSN_WEB": (REQUIRED, sentry_dsn, None),
    "SENTRY_AUTH_TOKEN": (
        REQUIRED,
        matches(r"sntryu_[0-9a-f]{64}|sntrys_\S{20,}|[0-9a-f]{64}"),
        sentry,
    ),
    "SENTRY_ORG": (REQUIRED, matches(SLUG), None),
    "SENTRY_PROJECT": (REQUIRED, matches(SLUG), None),
    "SERPAPI_API_KEY": (OPTIONAL, matches(r"[0-9a-f]{64}"), serpapi),
    "ULTRAMARINE_API_KEY": (OPTIONAL, matches(r"\S{20,}"), ultramarine),
    "ULTRAMARINE_BASE_URL": (OPTIONAL, https_url, None),
    "ULTRAMARINE_MODEL": (OPTIONAL, matches(r"\S+"), None),
    "HF_TOKEN": (OPTIONAL, matches(r"hf_[A-Za-z0-9]{30,}"), huggingface),
    "GEMINI_API_KEY": (UNUSED, None, None),
    "ELEVENLABS_API_KEY": (UNUSED, None, None),
    "TABPFN_TOKEN": (UNUSED, None, None),
}


def check(name):
    need, shape, call = KEYS[name]
    value = setting(name).get()
    if not value:
        return "EMPTY", need
    if need == UNUSED:
        return "OK", "present, unused, so not called"
    try:
        shaped = shape(value)
    except ValueError:  # urlsplit rejects some malformed URLs outright
        shaped = False
    if not shaped:
        return "FAIL", "unexpected shape"
    if call is None:
        return "OK", "shape ok"
    try:
        return "OK", f"shape ok, {call(value)}"
    except Failed as exc:
        return "FAIL", f"shape ok, {exc}"
    except Exception as exc:  # noqa: BLE001  messages can quote the key, URL or URI
        return "FAIL", f"shape ok, call raised {type(exc).__name__}"


def main():
    failed = False
    for name, (need, _, _) in KEYS.items():
        status, reason = check(name)
        print(f"{name:<22} {status:<5}  {reason}")
        failed |= status == "FAIL" or (status == "EMPTY" and need == REQUIRED)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
