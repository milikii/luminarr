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

    smoke_gate_match = re.search(
        r"- 最近一次聚合 smoke gate：(\d{4}-\d{2}-\d{2})，`([^`]+)`（`([^`]+)`）",
        text,
    )
    focused_cleanup_match = re.search(
        r"- 最近一次 cleanup 协议回归验证：(\d{4}-\d{2}-\d{2})，`([^`]+)`（`([^`]+)`）",
        text,
    )
    protocol_observation_match = re.search(r"- 当前 cleanup 协议观察：截至 (\d{4}-\d{2}-\d{2})，(.+)", text)
    assert smoke_gate_match is not None
    assert focused_cleanup_match is not None
    assert protocol_observation_match is not None
    smoke_gate_date = date.fromisoformat(smoke_gate_match.group(1))
    smoke_gate_result = smoke_gate_match.group(2)
    smoke_gate_command = smoke_gate_match.group(3)
    focused_cleanup_date = date.fromisoformat(focused_cleanup_match.group(1))
    focused_cleanup_result = focused_cleanup_match.group(2)
    focused_cleanup_command = focused_cleanup_match.group(3)
    protocol_observation_date = date.fromisoformat(protocol_observation_match.group(1))
    protocol_observation_text = protocol_observation_match.group(2)
    assert smoke_gate_date == conclusion_date
    assert focused_cleanup_date == conclusion_date
    assert protocol_observation_date == conclusion_date
    assert smoke_gate_result == "128 passed"
    assert smoke_gate_command == ".venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py"
    assert focused_cleanup_result == "223 passed, 91 deselected"
    assert (
        focused_cleanup_command
        == ".venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py "
        "tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py "
        "tests/test_personal_wechat_text.py tests/test_feishu_adapter.py "
        "tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup"
    )
    assert "未见协议回退" in protocol_observation_text
    assert "真实私聊 smoke 证据" in protocol_observation_text

    smoke_gate_checklist_match = re.search(
        r"- \[( |x)\] `tests/test_cleanup_cross_channel_smoke\.py` 持续通过",
        text,
    )
    protocol_regression_checklist_match = re.search(
        r"- \[( |x)\] cleanup discoverability / inspect / execution / rejection guidance / success follow-up / failure observability 没有协议回退",
        text,
    )
    assert smoke_gate_checklist_match is not None
    assert protocol_regression_checklist_match is not None
    smoke_gate_checklist_completed = smoke_gate_checklist_match.group(1) == "x"
    protocol_regression_checklist_completed = protocol_regression_checklist_match.group(1) == "x"
    assert smoke_gate_checklist_completed == ("passed" in smoke_gate_result)
    assert protocol_regression_checklist_completed == ("未见协议回退" in protocol_observation_text)

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
        assert "尚未到最早可结束日期" in conclusion
        assert end_match.group(1) in conclusion
    else:
        assert window_activity == "已到最早可结束日期，待补退出条件"
        assert "已到最早可结束日期" in conclusion
        assert end_match.group(1) in conclusion
