"""Tests for the skillbot package."""

import re

import skillbot


def test_version() -> None:
    assert re.match(r"\d+\.\d+\.\d+", skillbot.__version__)
