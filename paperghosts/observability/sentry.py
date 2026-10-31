"""Sentry for the API and the pipeline: off without a DSN, and nothing personal or secret
leaves this machine."""

import os
import re
import subprocess

import sentry_sdk

from paperghosts.config import setting

# a URL's query string, after scheme://host/path or a bare /path
QUERY = re.compile(r"((?:\w+:/)?/[^\s?#]*)\?[^\s#]*")
DROPPED_KEYS = {
    "query_string",
    "http.query",
    "lat",
    "lon",
    "lng",
    "latitude",
    "longitude",
    "coordinates",
}


def scrub(value):
    """Strips query strings and coordinate fields anywhere in an event."""
    if isinstance(value, str):
        return QUERY.sub(r"\1", value)
    if isinstance(value, dict):
        return {
            k: scrub(v) for k, v in value.items() if str(k).lower() not in DROPPED_KEYS
        }
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def release() -> str | None:
    """The commit this code is: SENTRY_RELEASE when the host sets it, else the checkout's git SHA."""
    if os.environ.get("SENTRY_RELEASE"):
        return os.environ["SENTRY_RELEASE"]
    try:
        found = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return found.stdout.strip() or None


def init_sentry(component: str) -> bool:
    """Starts Sentry for "api" or "pipeline". Without SENTRY_DSN it does nothing."""
    dsn = setting("SENTRY_DSN")
    if not dsn:
        return False
    sentry_sdk.init(
        dsn=dsn.get(),
        environment=component,  # the API and the pipeline share one project
        release=release(),
        server_name=component,  # the default is the host name, which can name its owner
        traces_sample_rate=1.0,
        # replaces the deprecated send_default_pii=False; fields left out default to on
        data_collection={
            "user_info": False,
            "cookies": {"mode": "off"},
            "http_headers": {"request": {"mode": "off"}},
            "http_bodies": [],
            "url_query_params": {"mode": "off"},
            "gen_ai": {"inputs": False, "outputs": False},
            "database_query_data": False,  # Mongo queries can hold near-me coordinates
            "stack_frame_variables": False,  # locals can hold keys, URIs and coordinates
        },
        before_send=lambda event, hint: scrub(event),
        before_send_transaction=lambda event, hint: scrub(event),
    )
    return True
