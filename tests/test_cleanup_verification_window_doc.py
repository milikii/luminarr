from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo


def test_cleanup_verification_window_doc_tracks_dates_channels_and_gate() -> None:
    text = Path("docs/CLEANUP_VERIFICATION_WINDOW.md").read_text(encoding="utf-8")

    status_match = re.search(r"- 当前状态：(进行中|已完成)", text)
    start_match = re.search(r"- 开始日期：(\d{4}-\d{2}-\d{2})", text)
    end_match = re.search(r"- 最早可结束日期：(\d{4}-\d{2}-\d{2})", text)
    activity_match = re.search(
        r"- 窗口活性：(未到最早可结束日期|已到最早可结束日期，待补退出条件|已满足退出条件)",
        text,
    )
    conclusion_match = re.search(r"- 当前结论：(.+)", text)
    conclusion_date_match = re.search(r"截至 (\d{4}-\d{2}-\d{2})", text)

    assert status_match is not None
    assert start_match is not None
    assert end_match is not None
    assert activity_match is not None
    assert conclusion_match is not None
    assert conclusion_date_match is not None

    window_status = status_match.group(1)
    conclusion = conclusion_match.group(1)
    start_date = date.fromisoformat(start_match.group(1))
    end_date = date.fromisoformat(end_match.group(1))
    window_activity = activity_match.group(1)
    conclusion_date = date.fromisoformat(conclusion_date_match.group(1))
    current_date = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    assert (end_date - start_date).days >= 7
    assert start_date <= conclusion_date <= current_date

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
    channel_checklist_rows = re.findall(
        r"- \[( |x)\] (Telegram|personal WeChat|Feishu|WeCom) 完成至少 1 次真实私聊 cleanup smoke",
        text,
    )
    assert len(channel_checklist_rows) == 4
    checklist_status_by_channel = {
        channel: (checked_flag == "x")
        for checked_flag, channel in channel_checklist_rows
    }
    for _, row_status, last_date in progress_rows:
        if row_status == "待验证":
            assert last_date == "-"
        else:
            date.fromisoformat(last_date)

    for channel, row_status, last_date in progress_rows:
        checklist_completed = checklist_status_by_channel[channel]
        if checklist_completed:
            assert row_status == "已完成"
            assert last_date != "-"
        else:
            assert row_status == "待验证"
            assert last_date == "-"

    window_completed_match = re.search(
        r"- \[( |x)\] 完成 (\d{4}-\d{2}-\d{2}) 到 (\d{4}-\d{2}-\d{2}) 的真实使用验证窗口",
        text,
    )
    assert window_completed_match is not None
    window_completed = window_completed_match.group(1) == "x"
    checklist_start_date = date.fromisoformat(window_completed_match.group(2))
    checklist_end_date = date.fromisoformat(window_completed_match.group(3))
    assert checklist_start_date == start_date
    assert checklist_end_date == end_date

    if window_status == "进行中":
        assert "暂未满足退出条件" in conclusion
        assert not window_completed
    else:
        assert "已满足退出条件" in conclusion
        assert window_completed
        assert all(row_status == "已完成" for _, row_status, _ in progress_rows)

    if window_status == "已完成":
        assert window_activity == "已满足退出条件"
    elif current_date < end_date:
        assert window_activity == "未到最早可结束日期"
    else:
        assert window_activity == "已到最早可结束日期，待补退出条件"
