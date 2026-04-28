from __future__ import annotations

import re
from collections.abc import Iterable, Mapping


def parse_prefixed_command_tail(text: str, *, prefix_pattern: str) -> str | None:
    cleaned_text = text.strip()
    if not cleaned_text:
        return None

    matched = re.match(rf"^(?:{prefix_pattern})(?:\s+(.*))?$", cleaned_text)
    if not matched:
        return None
    return (matched.group(1) or "").strip()


def match_command_action(tail: str, aliases_by_action: Mapping[str, Iterable[str]]) -> str | None:
    lowered_tail = tail.lower()
    for action, aliases in aliases_by_action.items():
        for alias in aliases:
            if lowered_tail == alias.lower() or tail == alias:
                return action
    return None


def match_command_action_argument(
    tail: str,
    aliases_by_action: Mapping[str, Iterable[str]],
) -> tuple[str, str] | None:
    head, separator, rest = tail.partition(" ")
    if not separator:
        return None
    action = match_command_action(head, aliases_by_action)
    if action is None:
        return None
    return action, rest.strip()
