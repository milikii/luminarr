from __future__ import annotations

from app.bot.cleanup_smoke_logging import (
    CleanupPrivateChatSmokeLogEntry,
    build_cleanup_private_chat_smoke_log_line,
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
