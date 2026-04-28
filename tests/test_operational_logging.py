from __future__ import annotations

from app.operational_logging import (
    emit_operational_log,
    format_operational_log_message,
    strip_ansi_escape,
    summarize_first_non_empty_line,
)


def test_emit_operational_log_uses_shared_formatter(capsys) -> None:
    emit_operational_log(
        title="测试失败",
        detail="reason=db down",
        fix_hint="检查 SQLite 后重试。",
    )

    output = capsys.readouterr().out
    assert "[测试失败]" in output
    assert "reason=db down" in output
    assert "[处理建议]" in output
    assert "检查 SQLite 后重试。" in output


def test_format_operational_log_message_keeps_title_detail_and_fix_hint_together() -> None:
    message = format_operational_log_message(
        title="测试失败",
        detail="reason=db down",
        fix_hint="检查 SQLite 后重试。",
    )

    assert "[测试失败]" in message
    assert "reason=db down" in message
    assert "[处理建议]" in message
    assert "检查 SQLite 后重试。" in message


def test_strip_ansi_escape_removes_color_codes() -> None:
    assert strip_ansi_escape("\033[31m[trace]\033[0m ok") == "[trace] ok"


def test_summarize_first_non_empty_line_returns_first_clean_line() -> None:
    assert summarize_first_non_empty_line("\n  first   line  \nsecond line") == "first line"
