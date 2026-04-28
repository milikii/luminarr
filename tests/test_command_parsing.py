from __future__ import annotations

from app.services.command_parsing import match_command_action, parse_prefixed_command_tail


def test_parse_prefixed_command_tail_returns_stripped_tail() -> None:
    assert parse_prefixed_command_tail("watchlist add dune", prefix_pattern=r"(?i:watchlist)") == "add dune"


def test_parse_prefixed_command_tail_supports_alternate_prefixes() -> None:
    assert parse_prefixed_command_tail("想看 add dune", prefix_pattern=r"(?i:watchlist)|想看") == "add dune"


def test_parse_prefixed_command_tail_rejects_missing_or_nonmatching_text() -> None:
    assert parse_prefixed_command_tail("", prefix_pattern=r"(?i:watchlist)") is None
    assert parse_prefixed_command_tail("status 1", prefix_pattern=r"(?i:watchlist)") is None


def test_match_command_action_supports_case_insensitive_and_raw_aliases() -> None:
    aliases = {
        "list": ("list", "列表"),
        "remove": ("remove", "rm", "删除"),
    }

    assert match_command_action("LIST", aliases) == "list"
    assert match_command_action("列表", aliases) == "list"
    assert match_command_action("rm", aliases) == "remove"
    assert match_command_action("unknown", aliases) is None
