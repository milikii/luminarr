from __future__ import annotations

from app.services.command_parsing import parse_prefixed_command_tail


def test_parse_prefixed_command_tail_returns_stripped_tail() -> None:
    assert parse_prefixed_command_tail("watchlist add dune", prefix_pattern=r"(?i:watchlist)") == "add dune"


def test_parse_prefixed_command_tail_supports_alternate_prefixes() -> None:
    assert parse_prefixed_command_tail("想看 add dune", prefix_pattern=r"(?i:watchlist)|想看") == "add dune"


def test_parse_prefixed_command_tail_rejects_missing_or_nonmatching_text() -> None:
    assert parse_prefixed_command_tail("", prefix_pattern=r"(?i:watchlist)") is None
    assert parse_prefixed_command_tail("status 1", prefix_pattern=r"(?i:watchlist)") is None
