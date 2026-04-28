from __future__ import annotations

import re


def parse_prefixed_command_tail(text: str, *, prefix_pattern: str) -> str | None:
    cleaned_text = text.strip()
    if not cleaned_text:
        return None

    matched = re.match(rf"^(?:{prefix_pattern})(?:\s+(.*))?$", cleaned_text)
    if not matched:
        return None
    return (matched.group(1) or "").strip()
