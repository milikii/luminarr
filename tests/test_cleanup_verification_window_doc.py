from __future__ import annotations

from datetime import date
from pathlib import Path
import re


def test_cleanup_verification_window_doc_tracks_dates_channels_and_gate() -> None:
    text = Path("docs/CLEANUP_VERIFICATION_WINDOW.md").read_text(encoding="utf-8")

    status_match = re.search(r"- 当前状态：(进行中|已完成)", text)
    start_match = re.search(r"- 开始日期：(\d{4}-\d{2}-\d{2})", text)
    end_match = re.search(r"- 最早可结束日期：(\d{4}-\d{2}-\d{2})", text)

    assert status_match is not None
    assert start_match is not None
    assert end_match is not None

    start_date = date.fromisoformat(start_match.group(1))
    end_date = date.fromisoformat(end_match.group(1))
    assert (end_date - start_date).days >= 7

    assert "`tests/test_cleanup_cross_channel_smoke.py`" in text
    assert "消息进来 -> shared runtime -> 文本回去" in text

    progress_rows = re.findall(
        r"\| (Telegram|personal WeChat|Feishu|WeCom) \| (待验证|已完成) \| ([0-9-]+|-) \|",
        text,
    )
    assert len(progress_rows) == 4
    assert {channel for channel, _, _ in progress_rows} == {
        "Telegram",
        "personal WeChat",
        "Feishu",
        "WeCom",
    }
    for _, status, last_date in progress_rows:
        if status == "待验证":
            assert last_date == "-"
        else:
            date.fromisoformat(last_date)
