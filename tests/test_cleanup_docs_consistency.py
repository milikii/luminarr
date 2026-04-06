from __future__ import annotations

from pathlib import Path
import re


def _extract_window_dates(text: str) -> tuple[str, str]:
    start_match = re.search(r"- 开始日期：(\d{4}-\d{2}-\d{2})", text)
    end_match = re.search(r"- 最早可结束日期：(\d{4}-\d{2}-\d{2})", text)
    assert start_match is not None
    assert end_match is not None
    return start_match.group(1), end_match.group(1)


def _extract_current_conclusion(text: str) -> str:
    conclusion_match = re.search(r"- 当前结论：(.+)", text)
    assert conclusion_match is not None
    return conclusion_match.group(1)


def _extract_window_activity(text: str) -> str:
    activity_match = re.search(
        r"- 窗口活性：(未到最早可结束日期|已到最早可结束日期，待补退出条件|已满足退出条件)",
        text,
    )
    assert activity_match is not None
    return activity_match.group(1)


def _extract_verification_evidence(text: str, label: str) -> tuple[str, str, str]:
    evidence_match = re.search(
        rf"- {re.escape(label)}：(\d{{4}}-\d{{2}}-\d{{2}})，`([^`]+)`（`([^`]+)`）",
        text,
    )
    assert evidence_match is not None
    return evidence_match.group(1), evidence_match.group(2), evidence_match.group(3)


def _extract_window_status(text: str) -> str:
    status_match = re.search(r"- 当前状态：(进行中|已完成)", text)
    assert status_match is not None
    return status_match.group(1)


def test_cleanup_verification_window_docs_stay_in_sync() -> None:
    next_step_text = Path("docs/NEXT_STEP.md").read_text(encoding="utf-8")
    status_text = Path("docs/STATUS.md").read_text(encoding="utf-8")
    window_text = Path("docs/CLEANUP_VERIFICATION_WINDOW.md").read_text(encoding="utf-8")

    start_date, end_date = _extract_window_dates(window_text)
    current_conclusion = _extract_current_conclusion(window_text)
    window_activity = _extract_window_activity(window_text)
    smoke_gate_date, smoke_gate_result, smoke_gate_command = _extract_verification_evidence(
        window_text,
        "最近一次聚合 smoke gate",
    )
    focused_cleanup_date, focused_cleanup_result, focused_cleanup_command = _extract_verification_evidence(
        window_text,
        "最近一次 cleanup 协议回归验证",
    )
    window_status = _extract_window_status(window_text)

    assert f"开始日期固定为 {start_date}" in status_text
    assert f"最早可结束日期固定为 {end_date}" in status_text
    assert f"- 窗口活性快照：{window_activity}" in status_text
    assert f"- 当前状态快照：{window_status}" in status_text
    assert f"- 当前结论快照：{current_conclusion}" in status_text
    assert f"- four-channel cleanup smoke tests：`{smoke_gate_result}`（{smoke_gate_date}，`{smoke_gate_command}`）" in status_text
    assert (
        f"- focused cleanup tests：`{focused_cleanup_result}`（{focused_cleanup_date}，"
        f"`{focused_cleanup_command}`）"
    ) in status_text

    for text in (next_step_text, status_text):
        assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in text
        assert "`tests/test_cleanup_cross_channel_smoke.py`" in text
        assert "真实私聊 smoke" in text
        assert "当前结论" in text
        assert "窗口活性" in text
        assert "cleanup 协议回归验证" in text
        assert "smoke gate / cleanup 协议两项" in text
        assert "chat-scoped task_ref -> jobs -> import correlation" in text
        assert "correlation-missing rejection guidance" in text
        assert "target-missing rejection guidance" in text
        assert "source-missing rejection guidance" in text
        assert "guard-rejected rejection guidance" in text

    window_progress_rows = re.findall(
        r"\| (Telegram|personal WeChat|Feishu|WeCom) \| (待验证|已完成) \| ([0-9-]+|-) \|",
        window_text,
    )
    status_progress_rows = re.findall(
        r"\| (Telegram|personal WeChat|Feishu|WeCom) \| (待验证|已完成) \| ([0-9-]+|-) \|",
        status_text,
    )
    assert len(window_progress_rows) == 4
    assert status_progress_rows == window_progress_rows
