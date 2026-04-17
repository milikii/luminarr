from __future__ import annotations

from pathlib import Path

from app.trace_logging import (
    TraceLogEntry,
    build_trace_log_line,
    configure_trace_log_file,
    log_trace_event,
    parse_trace_log_line,
)


def test_build_trace_log_line_and_parse_round_trip() -> None:
    log_line = build_trace_log_line(
        scope="workflow",
        event="approval_pending",
        result="created",
        channel="Telegram",
        workflow="add_to_downloader",
        action="query",
        stage="pending",
        chat_id=1001,
        user_id=2001,
        task_ref="1",
        task_id="selection:1",
        task_hash="hash-1",
        query="1",
        reply_text="下载待确认：Dune\n请发送 confirm 1 执行下载。",
        detail="Dune",
        timestamp_text="2026-04-17T12:00:00+08:00",
    )

    assert parse_trace_log_line(log_line) == TraceLogEntry(
        timestamp_text="2026-04-17T12:00:00+08:00",
        scope="workflow",
        event="approval_pending",
        result="created",
        channel="telegram",
        workflow="add_to_downloader",
        action="query",
        stage="pending",
        chat_id=1001,
        user_id=2001,
        task_ref="1",
        task_id="selection:1",
        task_hash="hash-1",
        query="1",
        reply_head="下载待确认：Dune",
        detail="Dune",
    )


def test_log_trace_event_appends_plain_line_to_file(tmp_path: Path, capsys) -> None:
    log_path = configure_trace_log_file(log_dir=tmp_path / "logs")

    log_trace_event(
        scope="private_chat",
        event="reply",
        result="sent",
        log_path=log_path,
        channel="wecom",
        action="reply",
        chat_id=1001,
        user_id=2001,
        query="dune",
        reply_text="搜索结果：dune\n1. Dune: Part Two",
        detail="search result",
    )

    captured = capsys.readouterr()
    assert "[trace]" in captured.out
    written_text = log_path.read_text(encoding="utf-8")
    assert "\033[" not in written_text
    parsed = parse_trace_log_line(written_text.strip())
    assert parsed is not None
    assert parsed.scope == "private_chat"
    assert parsed.event == "reply"
    assert parsed.channel == "wecom"
    assert parsed.reply_head == "搜索结果：dune"


def test_configure_trace_log_file_returns_none_when_log_dir_is_not_writable(tmp_path: Path, capsys) -> None:
    blocked_parent = tmp_path / "blocked-parent"
    blocked_parent.write_text("occupied", encoding="utf-8")

    assert configure_trace_log_file(log_dir=blocked_parent / "logs") is None

    captured = capsys.readouterr()
    assert "[trace 日志目录不可写]" in captured.out
    assert "[处理建议]" in captured.out
