from __future__ import annotations

from pathlib import Path

import app.bot.cleanup_smoke_logging as cleanup_smoke_logging
from app.bot.cleanup_smoke_logging import (
    CleanupPrivateChatSmokeLogEntry,
    build_cleanup_private_chat_smoke_log_line,
    configure_cleanup_private_chat_smoke_log_file,
    log_cleanup_private_chat_smoke,
    parse_cleanup_private_chat_smoke_log_line,
    resolve_cleanup_private_chat_action,
)


def test_resolve_cleanup_private_chat_action_supports_cleanup_variants() -> None:
    assert resolve_cleanup_private_chat_action("cleanup inspect cleanup-shortcut") == "cleanup_inspect"
    assert resolve_cleanup_private_chat_action("Cleanup Inspect cleanup-shortcut") == "cleanup_inspect"
    assert resolve_cleanup_private_chat_action("清理检查 cleanup-shortcut") == "cleanup_inspect"
    assert resolve_cleanup_private_chat_action("cleanup cleanup-shortcut") == "cleanup"
    assert resolve_cleanup_private_chat_action("清理 cleanup-shortcut") == "cleanup"
    assert resolve_cleanup_private_chat_action("我想看 Dune 2021") is None


def test_build_cleanup_private_chat_smoke_log_line_uses_first_reply_line() -> None:
    log_line = build_cleanup_private_chat_smoke_log_line(
        channel="Telegram",
        query="cleanup inspect cleanup-shortcut",
        reply_text="清理预检结果：\n查询引用: cleanup-shortcut\n任务 ID: task-1",
        chat_id=123,
        user_id=456,
        date_text="2026-04-12",
    )

    assert log_line is not None
    assert "[cleanup 私聊 smoke]" in log_line
    assert "date=2026-04-12" in log_line
    assert "channel=telegram" in log_line
    assert "action=cleanup_inspect" in log_line
    assert 'query="cleanup inspect cleanup-shortcut"' in log_line
    assert 'reply_head="清理预检结果："' in log_line


def test_parse_cleanup_private_chat_smoke_log_line_returns_structured_entry() -> None:
    log_line = build_cleanup_private_chat_smoke_log_line(
        channel="feishu",
        query="cleanup cleanup-shortcut",
        reply_text="已清理下载源资产。\n任务 ID: task-1",
        chat_id=789,
        user_id=321,
        date_text="2026-04-12",
    )

    assert parse_cleanup_private_chat_smoke_log_line("not a cleanup smoke line") is None
    assert parse_cleanup_private_chat_smoke_log_line(log_line or "") == CleanupPrivateChatSmokeLogEntry(
        date_text="2026-04-12",
        channel="feishu",
        action="cleanup",
        chat_id=789,
        user_id=321,
        query="cleanup cleanup-shortcut",
        reply_head="已清理下载源资产。",
    )


def test_log_cleanup_private_chat_smoke_appends_plain_line_to_configured_log_file(
    tmp_path: Path,
    capsys,
) -> None:
    log_path = configure_cleanup_private_chat_smoke_log_file(log_dir=tmp_path / "logs")
    log_cleanup_private_chat_smoke(
        channel="telegram",
        query="cleanup inspect cleanup-shortcut",
        reply_text="清理预检结果：\n任务 ID: 87",
        chat_id=1001,
        user_id=2001,
        log_path=log_path,
    )

    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke]" in captured.out
    written_text = log_path.read_text(encoding="utf-8")
    assert "\033[" not in written_text
    assert "[cleanup 私聊 smoke]" in written_text
    assert 'query="cleanup inspect cleanup-shortcut"' in written_text
    assert 'reply_head="清理预检结果："' in written_text


def test_log_cleanup_private_chat_smoke_prints_fix_hint_when_log_file_is_not_writable(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    blocked_parent = tmp_path / "blocked-parent"
    blocked_parent.write_text("occupied", encoding="utf-8")
    log_path = blocked_parent / "cleanup-private-chat-smoke.log"

    log_cleanup_private_chat_smoke(
        channel="telegram",
        query="cleanup cleanup-shortcut",
        reply_text="已清理下载源资产。",
        chat_id=1001,
        user_id=2001,
        log_path=log_path,
    )

    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke 日志落盘失败]" in captured.out
    assert "[处理建议]" in captured.out


def test_configure_cleanup_private_chat_smoke_log_file_returns_none_when_log_dir_is_not_writable(
    tmp_path: Path,
    capsys,
) -> None:
    blocked_parent = tmp_path / "blocked-parent"
    blocked_parent.write_text("occupied", encoding="utf-8")
    assert configure_cleanup_private_chat_smoke_log_file(log_dir=blocked_parent / "logs") is None
    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke 日志目录不可写]" in captured.out
    assert "[处理建议]" in captured.out
