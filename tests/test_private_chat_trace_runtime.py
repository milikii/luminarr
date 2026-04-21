from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from app.bot.private_chat_trace_runtime import prepare_private_chat_reply_with_trace
from app.trace_logging import TRACE_LOG_PATH_BOT_DATA_KEY, parse_trace_log_line


def test_prepare_private_chat_reply_with_trace_logs_inbound_and_reply(tmp_path: Path) -> None:
    reply_func = AsyncMock(return_value={"ok": True})
    log_path = tmp_path / "trace.log"
    traced_reply = prepare_private_chat_reply_with_trace(
        bot_data={TRACE_LOG_PATH_BOT_DATA_KEY: log_path},
        reply_func=reply_func,
        channel="telegram",
        chat_id=1001,
        user_id=2001,
        query="dune",
    )

    result = asyncio.run(traced_reply("搜索：dune ✓\n▸ 候选结果"))

    assert result == {"ok": True}
    reply_func.assert_awaited_once_with("搜索：dune ✓\n▸ 候选结果")
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    parsed_entries = [parse_trace_log_line(line) for line in lines]

    assert [entry.event if entry is not None else None for entry in parsed_entries] == ["inbound", "reply"]
    assert parsed_entries[0] is not None
    assert parsed_entries[0].channel == "telegram"
    assert parsed_entries[0].query == "dune"
    assert parsed_entries[1] is not None
    assert parsed_entries[1].reply_head == "搜索：dune ✓"


def test_prepare_private_chat_reply_with_trace_keeps_reply_when_trace_disabled() -> None:
    reply_func = AsyncMock(return_value="ok")
    traced_reply = prepare_private_chat_reply_with_trace(
        bot_data={},
        reply_func=reply_func,
        channel="personal_wechat",
        chat_id=1001,
        user_id=2001,
        query="dune",
    )

    result = asyncio.run(traced_reply("搜索：dune ✓"))

    assert result == "ok"
    reply_func.assert_awaited_once_with("搜索：dune ✓")
