"""Centralized user-facing strings for Skillbot.

Strings are loaded from strings.json and can be retrieved with optional
.format() substitution via keyword arguments.
"""

from __future__ import annotations

import json
from pathlib import Path

_STRINGS: dict[str, object] = {}


def _load_strings() -> dict[str, object]:
    """Load strings from strings.json (cached)."""
    global _STRINGS
    if not _STRINGS:
        path = Path(__file__).parent / "strings.json"
        _STRINGS = json.loads(path.read_text())
    return _STRINGS


def get(key: str, **kwargs: object) -> str:
    """Get a string by dot-separated key (e.g. 'banner.tagline').

    Supports .format() substitution via keyword arguments.
    """
    data = _load_strings()
    parts = key.split(".")
    value: object = data
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return key  # Key not found, return key as fallback
    result = str(value) if value is not None else key
    if kwargs:
        try:
            return result.format(**kwargs)
        except KeyError:
            return result
    return result
