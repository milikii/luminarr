from __future__ import annotations

import re


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi_escape(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def summarize_first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        cleaned_line = re.sub(r"\s+", " ", line.strip())
        if cleaned_line:
            return cleaned_line
    return "-"


def format_operational_log_message(*, title: str, detail: str, fix_hint: str) -> str:
    return f"\033[31m[{title}]\033[0m {detail}\n\033[33m[处理建议]\033[0m {fix_hint}"


def emit_operational_log(*, title: str, detail: str, fix_hint: str) -> None:
    print(format_operational_log_message(title=title, detail=detail, fix_hint=fix_hint), flush=True)
