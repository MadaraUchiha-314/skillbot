"""Tests for the hello module."""

from skillbot.hello import hello


def test_hello_default() -> None:
    assert hello() == "Hello, World!"


def test_hello_with_name() -> None:
    assert hello("Skillbot") == "Hello, Skillbot!"


def test_hello_empty_string() -> None:
    assert hello("") == "Hello, !"
