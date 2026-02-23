"""Skillbot - A Python package."""

__version__ = "0.2.0"

from skillbot.hello import hello


def main() -> None:
    """Entry point for the skillbot CLI."""
    print(hello())


__all__ = ["hello", "main"]
