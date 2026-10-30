"""Settings from the environment, falling back to the repo's .env.

Values come back wrapped in Secret, so printing or logging one never shows it.
"""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

# The owner's .env names the Ultramarine key PAPERINSTRUMENTS_API_KEY (decision 12).
ALIASES = {"ULTRAMARINE_API_KEY": "PAPERINSTRUMENTS_API_KEY"}


class Secret:
    """A setting's value; repr, str and f-strings show only whether it is set."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)

    def __repr__(self) -> str:
        return "Secret(set)" if self._value else "Secret(empty)"

    __str__ = __repr__


def read_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE pairs; blanks, # comments and lines without = are skipped."""
    values = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            name, eq, value = line.strip().partition("=")
            if not eq or name.startswith("#"):
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[name.strip()] = value
    return values


def setting(name: str) -> Secret:
    """The environment wins over .env, so Render's settings apply where there is no .env."""
    file = read_env_file(ENV_FILE)
    for key in (name, ALIASES.get(name)):
        if key and (value := os.environ.get(key) or file.get(key)):
            return Secret(value)
    return Secret("")
