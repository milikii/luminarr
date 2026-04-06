from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import pytest


def _assert_active_window_dates_are_current(
    *,
    window_status: str,
    current_date: date,
    conclusion_date: date,
    smoke_gate_date: date,
    focused_cleanup_date: date,
    docs_gate_date: date,
    protocol_observation_date: date,
) -> None:
    if window_status != "进行中":
        return
    assert conclusion_date == current_date
    assert smoke_gate_date == current_date
    assert focused_cleanup_date == current_date
    assert docs_gate_date == current_date
    assert protocol_observation_date == current_date


def _assert_completed_window_not_before_end_date(
    *,
    window_status: str,
    current_date: date,
    end_date: date,
) -> None:
    if window_status != "已完成":
        return
    assert current_date >= end_date


def _assert_completed_channel_dates_stay_within_window_snapshot(
    *,
    progress_rows: list[tuple[str, str, str]],
    start_date: date,
    conclusion_date: date,
) -> None:
    for _, row_status, last_date in progress_rows:
        if row_status != "已完成":
            continue
        channel_date = date.fromisoformat(last_date)
        assert start_date <= channel_date <= conclusion_date


def _assert_window_completes_immediately_when_exit_conditions_are_met(
    *,
    current_date: date,
    end_date: date,
    window_status: str,
    window_activity: str,
    conclusion: str,
    window_completed: bool,
    progress_rows: list[tuple[str, str, str]],
    smoke_gate_checklist_completed: bool,
    protocol_regression_checklist_completed: bool,
    docs_gate_checklist_completed: bool,
) -> None:
    exit_conditions_met = (
        current_date >= end_date
        and all(row_status == "已完成" for _, row_status, _ in progress_rows)
        and smoke_gate_checklist_completed
        and protocol_regression_checklist_completed
        and docs_gate_checklist_completed
    )
    if not exit_conditions_met:
        return
    assert window_status == "已完成"
    assert window_activity == "已满足退出条件"
    assert window_completed
    assert "已满足退出条件" in conclusion


def _assert_completed_window_keeps_all_evidence_checks_completed(
    *,
    window_status: str,
    smoke_gate_checklist_completed: bool,
    protocol_regression_checklist_completed: bool,
    docs_gate_checklist_completed: bool,
) -> None:
    if window_status != "已完成":
        return
    assert smoke_gate_checklist_completed
    assert protocol_regression_checklist_completed
    assert docs_gate_checklist_completed


def _assert_protocol_observation_mentions_pending_channel_gap_when_needed(
    *,
    progress_rows: list[tuple[str, str, str]],
    protocol_observation_text: str,
) -> None:
    has_pending_channel = any(row_status == "待验证" for _, row_status, _ in progress_rows)
    if not has_pending_channel:
        return
    assert "当前缺口只剩四渠道真实私聊 smoke 证据" in protocol_observation_text


def _assert_protocol_observation_drops_pending_channel_gap_when_resolved(
    *,
    progress_rows: list[tuple[str, str, str]],
    protocol_observation_text: str,
) -> None:
    has_pending_channel = any(row_status == "待验证" for _, row_status, _ in progress_rows)
    if has_pending_channel:
        return
    assert "当前缺口只剩四渠道真实私聊 smoke 证据" not in protocol_observation_text


def _assert_protocol_observation_mentions_non_channel_gaps_when_they_are_the_remaining_blockers(
    *,
    progress_rows: list[tuple[str, str, str]],
    smoke_gate_checklist_completed: bool,
    protocol_regression_checklist_completed: bool,
    docs_gate_checklist_completed: bool,
    protocol_observation_text: str,
) -> None:
    has_pending_channel = any(row_status == "待验证" for _, row_status, _ in progress_rows)
    if has_pending_channel:
        return
    if not smoke_gate_checklist_completed:
        assert "smoke gate" in protocol_observation_text
    if not protocol_regression_checklist_completed:
        assert "cleanup 协议" in protocol_observation_text
    if not docs_gate_checklist_completed:
        assert "verification docs gate" in protocol_observation_text


def _assert_protocol_observation_keeps_only_no_regression_when_only_end_date_blocks_completion(
    *,
    progress_rows: list[tuple[str, str, str]],
    smoke_gate_checklist_completed: bool,
    protocol_regression_checklist_completed: bool,
    docs_gate_checklist_completed: bool,
    current_date: date,
    end_date: date,
    protocol_observation_text: str,
) -> None:
    has_pending_channel = any(row_status == "待验证" for _, row_status, _ in progress_rows)
    has_non_channel_gap = not (
        smoke_gate_checklist_completed
        and protocol_regression_checklist_completed
        and docs_gate_checklist_completed
    )
    if has_pending_channel or has_non_channel_gap or current_date >= end_date:
        return
    assert "未见协议回退" in protocol_observation_text
    assert "缺口" not in protocol_observation_text
    assert "smoke gate" not in protocol_observation_text
    assert "cleanup 协议" not in protocol_observation_text
    assert "verification docs gate" not in protocol_observation_text


def _assert_completed_protocol_observation_drops_gap_wording(
    *,
    window_status: str,
    protocol_observation_text: str,
) -> None:
    if window_status != "已完成":
        return
    assert "未见协议回退" in protocol_observation_text
    assert "待补" not in protocol_observation_text
    assert "缺口" not in protocol_observation_text
    assert "smoke gate" not in protocol_observation_text
    assert "verification docs gate" not in protocol_observation_text


def _assert_conclusion_mentions_pending_channel_gap_when_needed(
    *,
    progress_rows: list[tuple[str, str, str]],
    conclusion: str,
) -> None:
    has_pending_channel = any(row_status == "待验证" for _, row_status, _ in progress_rows)
    if not has_pending_channel:
        return
    assert "真实私聊 cleanup smoke" in conclusion
    assert "待补" in conclusion


def _assert_conclusion_drops_pending_channel_gap_when_resolved(
    *,
    progress_rows: list[tuple[str, str, str]],
    conclusion: str,
) -> None:
    has_pending_channel = any(row_status == "待验证" for _, row_status, _ in progress_rows)
    if has_pending_channel:
        return
    assert "真实私聊 cleanup smoke 仍待补" not in conclusion
    assert "真实私聊 cleanup smoke 记录仍待补" not in conclusion


def _assert_conclusion_mentions_non_channel_gaps_when_they_are_the_remaining_blockers(
    *,
    progress_rows: list[tuple[str, str, str]],
    smoke_gate_checklist_completed: bool,
    protocol_regression_checklist_completed: bool,
    docs_gate_checklist_completed: bool,
    conclusion: str,
) -> None:
    has_pending_channel = any(row_status == "待验证" for _, row_status, _ in progress_rows)
    if has_pending_channel:
        return
    if not smoke_gate_checklist_completed:
        assert "smoke gate" in conclusion
    if not protocol_regression_checklist_completed:
        assert "cleanup 协议" in conclusion
    if not docs_gate_checklist_completed:
        assert "verification docs gate" in conclusion


def _assert_conclusion_only_mentions_end_date_blocker_when_it_is_the_last_remaining_gap(
    *,
    progress_rows: list[tuple[str, str, str]],
    smoke_gate_checklist_completed: bool,
    protocol_regression_checklist_completed: bool,
    docs_gate_checklist_completed: bool,
    current_date: date,
    end_date: date,
    conclusion: str,
) -> None:
    has_pending_channel = any(row_status == "待验证" for _, row_status, _ in progress_rows)
    has_non_channel_gap = not (
        smoke_gate_checklist_completed
        and protocol_regression_checklist_completed
        and docs_gate_checklist_completed
    )
    if has_pending_channel or has_non_channel_gap or current_date >= end_date:
        return
    assert "尚未到最早可结束日期" in conclusion
    assert end_date.isoformat() in conclusion
    assert "smoke gate" not in conclusion
    assert "cleanup 协议" not in conclusion
    assert "verification docs gate" not in conclusion


def _assert_completed_conclusion_drops_gap_wording(
    *,
    window_status: str,
    conclusion: str,
) -> None:
    if window_status != "已完成":
        return
    assert "已满足退出条件" in conclusion
    assert "待补" not in conclusion
    assert "缺口" not in conclusion
    assert "smoke gate" not in conclusion
    assert "cleanup 协议" not in conclusion
    assert "verification docs gate" not in conclusion
    assert "尚未到最早可结束日期" not in conclusion
    assert "已到最早可结束日期" not in conclusion


def _assert_channel_progress_notes_match_status(
    *,
    start_date: date,
    progress_rows_with_notes: list[tuple[str, str, str, str]],
) -> None:
    for _, row_status, last_date, note in progress_rows_with_notes:
        if row_status == "待验证":
            assert last_date == "-"
            assert start_date.isoformat() in note
            assert "启动验证窗口" in note
            assert "待补真实私聊 smoke 记录" in note
            continue
        assert last_date != "-"
        assert last_date in note
        assert "已完成真实私聊 smoke" in note
        assert "启动验证窗口" not in note
        assert "待补真实私聊 smoke 记录" not in note


def test_protocol_observation_requires_named_non_channel_gaps_after_channel_gap_is_closed() -> None:
    resolved_progress_rows = [
        ("Telegram", "已完成", "2026-04-05"),
        ("personal WeChat", "已完成", "2026-04-05"),
        ("Feishu", "已完成", "2026-04-05"),
        ("WeCom", "已完成", "2026-04-05"),
    ]

    _assert_protocol_observation_mentions_non_channel_gaps_when_they_are_the_remaining_blockers(
        progress_rows=resolved_progress_rows,
        smoke_gate_checklist_completed=False,
        protocol_regression_checklist_completed=True,
        docs_gate_checklist_completed=False,
        protocol_observation_text="cleanup discoverability 未见协议回退；剩余缺口是 smoke gate 和 verification docs gate。",
    )

    with pytest.raises(AssertionError):
        _assert_protocol_observation_mentions_non_channel_gaps_when_they_are_the_remaining_blockers(
            progress_rows=resolved_progress_rows,
            smoke_gate_checklist_completed=False,
            protocol_regression_checklist_completed=True,
            docs_gate_checklist_completed=False,
            protocol_observation_text="cleanup discoverability 未见协议回退。",
        )


def test_completed_protocol_observation_drops_gap_wording() -> None:
    _assert_completed_protocol_observation_drops_gap_wording(
        window_status="已完成",
        protocol_observation_text="cleanup discoverability / inspect / execution 未见协议回退。",
    )

    with pytest.raises(AssertionError):
        _assert_completed_protocol_observation_drops_gap_wording(
            window_status="已完成",
            protocol_observation_text="cleanup discoverability / inspect / execution 未见协议回退；当前缺口是 verification docs gate。",
        )


def test_pending_channel_notes_keep_window_start_date_anchor() -> None:
    _assert_channel_progress_notes_match_status(
        start_date=date(2026, 4, 5),
        progress_rows_with_notes=[
            ("Telegram", "待验证", "-", "2026-04-05 启动验证窗口，待补真实私聊 smoke 记录"),
            ("personal WeChat", "已完成", "2026-04-06", "2026-04-06 已完成真实私聊 smoke"),
        ],
    )

    with pytest.raises(AssertionError):
        _assert_channel_progress_notes_match_status(
            start_date=date(2026, 4, 5),
            progress_rows_with_notes=[
                ("Telegram", "待验证", "-", "待补真实私聊 smoke 记录"),
            ],
        )

    with pytest.raises(AssertionError):
        _assert_channel_progress_notes_match_status(
            start_date=date(2026, 4, 5),
            progress_rows_with_notes=[
                ("Telegram", "已完成", "2026-04-06", "已完成真实私聊 smoke"),
            ],
        )


def test_conclusion_keeps_only_end_date_blocker_when_everything_else_is_done_early() -> None:
    resolved_progress_rows = [
        ("Telegram", "已完成", "2026-04-05"),
        ("personal WeChat", "已完成", "2026-04-05"),
        ("Feishu", "已完成", "2026-04-05"),
        ("WeCom", "已完成", "2026-04-05"),
    ]

    _assert_conclusion_only_mentions_end_date_blocker_when_it_is_the_last_remaining_gap(
        progress_rows=resolved_progress_rows,
        smoke_gate_checklist_completed=True,
        protocol_regression_checklist_completed=True,
        docs_gate_checklist_completed=True,
        current_date=date(2026, 4, 6),
        end_date=date(2026, 4, 12),
        conclusion="验证窗口仍在进行中；截至 2026-04-06，尚未到最早可结束日期 2026-04-12，暂未满足退出条件。",
    )

    with pytest.raises(AssertionError):
        _assert_conclusion_only_mentions_end_date_blocker_when_it_is_the_last_remaining_gap(
            progress_rows=resolved_progress_rows,
            smoke_gate_checklist_completed=True,
            protocol_regression_checklist_completed=True,
            docs_gate_checklist_completed=True,
            current_date=date(2026, 4, 6),
            end_date=date(2026, 4, 12),
            conclusion=(
                "验证窗口仍在进行中；截至 2026-04-06，尚未到最早可结束日期 2026-04-12，"
                "但 smoke gate 仍待补，暂未满足退出条件。"
            ),
        )


def test_protocol_observation_keeps_only_no_regression_when_everything_else_is_done_early() -> None:
    resolved_progress_rows = [
        ("Telegram", "已完成", "2026-04-05"),
        ("personal WeChat", "已完成", "2026-04-05"),
        ("Feishu", "已完成", "2026-04-05"),
        ("WeCom", "已完成", "2026-04-05"),
    ]

    _assert_protocol_observation_keeps_only_no_regression_when_only_end_date_blocks_completion(
        progress_rows=resolved_progress_rows,
        smoke_gate_checklist_completed=True,
        protocol_regression_checklist_completed=True,
        docs_gate_checklist_completed=True,
        current_date=date(2026, 4, 6),
        end_date=date(2026, 4, 12),
        protocol_observation_text="cleanup discoverability / inspect / execution 未见协议回退。",
    )

    with pytest.raises(AssertionError):
        _assert_protocol_observation_keeps_only_no_regression_when_only_end_date_blocks_completion(
            progress_rows=resolved_progress_rows,
            smoke_gate_checklist_completed=True,
            protocol_regression_checklist_completed=True,
            docs_gate_checklist_completed=True,
            current_date=date(2026, 4, 6),
            end_date=date(2026, 4, 12),
            protocol_observation_text=(
                "cleanup discoverability / inspect / execution 未见协议回退；"
                "当前缺口是 smoke gate 和 verification docs gate。"
            ),
        )


def test_completed_conclusion_drops_pending_and_gap_wording() -> None:
    _assert_completed_conclusion_drops_gap_wording(
        window_status="已完成",
        conclusion="验证窗口已满足退出条件；截至 2026-04-12，已满足退出条件。",
    )

    with pytest.raises(AssertionError):
        _assert_completed_conclusion_drops_gap_wording(
            window_status="已完成",
            conclusion="验证窗口已满足退出条件；截至 2026-04-12，已满足退出条件，但 verification docs gate 缺口仍待补。",
        )


def test_cleanup_verification_window_doc_tracks_dates_channels_and_gate() -> None:
    text = Path("docs/CLEANUP_VERIFICATION_WINDOW.md").read_text(encoding="utf-8")

    title_match = re.search(
        r"^# Cleanup verification window \((\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})\) \(v\d+\)$",
        text,
        re.MULTILINE,
    )
    status_match = re.search(r"- 当前状态：(进行中|已完成)", text)
    start_match = re.search(r"- 开始日期：(\d{4}-\d{2}-\d{2})", text)
    end_match = re.search(r"- 最早可结束日期：(\d{4}-\d{2}-\d{2})", text)
    activity_match = re.search(
        r"- 窗口活性：(未到最早可结束日期|已到最早可结束日期，待补退出条件|已满足退出条件)",
        text,
    )
    conclusion_match = re.search(r"- 当前结论：(.+)", text)
    conclusion_date_match = re.search(r"截至 (\d{4}-\d{2}-\d{2})", text)

    assert title_match is not None
    assert status_match is not None
    assert start_match is not None
    assert end_match is not None
    assert activity_match is not None
    assert conclusion_match is not None
    assert conclusion_date_match is not None

    title_start_date = date.fromisoformat(title_match.group(1))
    title_end_date = date.fromisoformat(title_match.group(2))
    window_status = status_match.group(1)
    conclusion = conclusion_match.group(1)
    start_date = date.fromisoformat(start_match.group(1))
    end_date = date.fromisoformat(end_match.group(1))
    window_activity = activity_match.group(1)
    conclusion_date = date.fromisoformat(conclusion_date_match.group(1))
    current_date = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    assert (end_date - start_date).days >= 7
    assert title_start_date == start_date
    assert title_end_date == end_date
    assert start_date <= conclusion_date <= current_date

    smoke_gate_match = re.search(
        r"- 最近一次聚合 smoke gate：(\d{4}-\d{2}-\d{2})，`([^`]+)`（`([^`]+)`）",
        text,
    )
    focused_cleanup_match = re.search(
        r"- 最近一次 cleanup 协议回归验证：(\d{4}-\d{2}-\d{2})，`([^`]+)`（`([^`]+)`）",
        text,
    )
    docs_gate_match = re.search(
        r"- 最近一次 verification docs gate：(\d{4}-\d{2}-\d{2})，`([^`]+)`（`([^`]+)`）",
        text,
    )
    protocol_observation_match = re.search(r"- 当前 cleanup 协议观察：截至 (\d{4}-\d{2}-\d{2})，(.+)", text)
    assert smoke_gate_match is not None
    assert focused_cleanup_match is not None
    assert docs_gate_match is not None
    assert protocol_observation_match is not None
    smoke_gate_date = date.fromisoformat(smoke_gate_match.group(1))
    smoke_gate_result = smoke_gate_match.group(2)
    smoke_gate_command = smoke_gate_match.group(3)
    focused_cleanup_date = date.fromisoformat(focused_cleanup_match.group(1))
    focused_cleanup_result = focused_cleanup_match.group(2)
    focused_cleanup_command = focused_cleanup_match.group(3)
    docs_gate_date = date.fromisoformat(docs_gate_match.group(1))
    docs_gate_result = docs_gate_match.group(2)
    docs_gate_command = docs_gate_match.group(3)
    protocol_observation_date = date.fromisoformat(protocol_observation_match.group(1))
    protocol_observation_text = protocol_observation_match.group(2)
    assert smoke_gate_date == conclusion_date
    assert focused_cleanup_date == conclusion_date
    assert docs_gate_date == conclusion_date
    assert protocol_observation_date == conclusion_date
    assert "correlation-query-failure observability" in protocol_observation_text
    assert "source-type-unsupported blocked-log observability" in protocol_observation_text
    assert "success-event-append-failure observability" in protocol_observation_text
    assert "delete-failure observability" in protocol_observation_text
    assert "correlation-missing unresolved-identity blank display" in protocol_observation_text
    assert "correlation-missing inspect identity resolution" in protocol_observation_text
    assert "correlation-missing rejection guidance" in protocol_observation_text
    assert "post-cleanup cleanup inspect confirmation" in protocol_observation_text
    assert "chat-scoped task_ref post-cleanup cleanup inspect confirmation" in protocol_observation_text
    assert "chat-scoped task_ref target-missing cleanup inspect follow-up guidance" in protocol_observation_text
    assert "chat-scoped task_ref source-missing cleanup inspect follow-up guidance" in protocol_observation_text
    assert "chat-scoped task_ref source-type-unsupported cleanup inspect follow-up guidance" in protocol_observation_text
    assert "source-type-unsupported rejection guidance" in protocol_observation_text
    assert "missing-structured-import-correlation identity retention" in protocol_observation_text
    assert "correlation-query-failure identity retention" in protocol_observation_text
    _assert_active_window_dates_are_current(
        window_status=window_status,
        current_date=current_date,
        conclusion_date=conclusion_date,
        smoke_gate_date=smoke_gate_date,
        focused_cleanup_date=focused_cleanup_date,
        docs_gate_date=docs_gate_date,
        protocol_observation_date=protocol_observation_date,
    )
    assert smoke_gate_result == "336 passed"
    assert smoke_gate_command == ".venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py"
    assert focused_cleanup_result == "444 passed, 91 deselected"
    assert (
        focused_cleanup_command
        == ".venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py "
        "tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py "
        "tests/test_personal_wechat_text.py tests/test_feishu_adapter.py "
        "tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup"
    )
    assert docs_gate_result == "360 passed"
    assert (
        docs_gate_command
        == ".venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py "
        "tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py"
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
    docs_gate_checklist_match = re.search(
        r"- \[( |x)\] verification docs gate 持续通过",
        text,
    )
    assert smoke_gate_checklist_match is not None
    assert protocol_regression_checklist_match is not None
    assert docs_gate_checklist_match is not None
    smoke_gate_checklist_completed = smoke_gate_checklist_match.group(1) == "x"
    protocol_regression_checklist_completed = protocol_regression_checklist_match.group(1) == "x"
    docs_gate_checklist_completed = docs_gate_checklist_match.group(1) == "x"
    assert smoke_gate_checklist_completed == ("passed" in smoke_gate_result)
    assert protocol_regression_checklist_completed == ("未见协议回退" in protocol_observation_text)
    assert docs_gate_checklist_completed == ("passed" in docs_gate_result)

    assert "`tests/test_cleanup_cross_channel_smoke.py`" in text
    assert "verification docs gate" in text
    assert "消息进来 -> shared runtime -> 文本回去" in text
    assert "同步到当天日期" in text
    assert "不得早于最早可结束日期" in text
    assert "不得早于窗口开始日期" in text
    assert "不得晚于当前结论快照日期" in text
    assert "## PT 做种 guardrail 评估" in text
    assert "pt_min_seed_hours" in text
    assert "下载器 seeding 信息" in text
    assert "当前 cleanup guardrail 是否读取下载器做种状态：未覆盖" in text
    assert "不得把删除仍在做种中的 PT 资产视为已验证稳定能力" in text
    assert "本窗口只记录风险，不扩 cleanup 行为" in text

    progress_rows = re.findall(
        r"\| (Telegram|personal WeChat|Feishu|WeCom) \| (待验证|已完成) \| ([0-9-]+|-) \|",
        text,
    )
    progress_rows_with_notes = re.findall(
        r"\| (Telegram|personal WeChat|Feishu|WeCom) \| (待验证|已完成) \| ([0-9-]+|-) \| ([^|]+) \|",
        text,
    )
    assert len(progress_rows) == 4
    assert len(progress_rows_with_notes) == 4
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
    _assert_completed_channel_dates_stay_within_window_snapshot(
        progress_rows=progress_rows,
        start_date=start_date,
        conclusion_date=conclusion_date,
    )
    _assert_protocol_observation_mentions_pending_channel_gap_when_needed(
        progress_rows=progress_rows,
        protocol_observation_text=protocol_observation_text,
    )
    _assert_protocol_observation_drops_pending_channel_gap_when_resolved(
        progress_rows=progress_rows,
        protocol_observation_text=protocol_observation_text,
    )
    _assert_completed_protocol_observation_drops_gap_wording(
        window_status=window_status,
        protocol_observation_text=protocol_observation_text,
    )
    _assert_protocol_observation_mentions_non_channel_gaps_when_they_are_the_remaining_blockers(
        progress_rows=progress_rows,
        smoke_gate_checklist_completed=smoke_gate_checklist_completed,
        protocol_regression_checklist_completed=protocol_regression_checklist_completed,
        docs_gate_checklist_completed=docs_gate_checklist_completed,
        protocol_observation_text=protocol_observation_text,
    )
    _assert_protocol_observation_keeps_only_no_regression_when_only_end_date_blocks_completion(
        progress_rows=progress_rows,
        smoke_gate_checklist_completed=smoke_gate_checklist_completed,
        protocol_regression_checklist_completed=protocol_regression_checklist_completed,
        docs_gate_checklist_completed=docs_gate_checklist_completed,
        current_date=current_date,
        end_date=end_date,
        protocol_observation_text=protocol_observation_text,
    )
    _assert_conclusion_mentions_pending_channel_gap_when_needed(
        progress_rows=progress_rows,
        conclusion=conclusion,
    )
    _assert_conclusion_drops_pending_channel_gap_when_resolved(
        progress_rows=progress_rows,
        conclusion=conclusion,
    )
    _assert_conclusion_mentions_non_channel_gaps_when_they_are_the_remaining_blockers(
        progress_rows=progress_rows,
        smoke_gate_checklist_completed=smoke_gate_checklist_completed,
        protocol_regression_checklist_completed=protocol_regression_checklist_completed,
        docs_gate_checklist_completed=docs_gate_checklist_completed,
        conclusion=conclusion,
    )
    _assert_conclusion_only_mentions_end_date_blocker_when_it_is_the_last_remaining_gap(
        progress_rows=progress_rows,
        smoke_gate_checklist_completed=smoke_gate_checklist_completed,
        protocol_regression_checklist_completed=protocol_regression_checklist_completed,
        docs_gate_checklist_completed=docs_gate_checklist_completed,
        current_date=current_date,
        end_date=end_date,
        conclusion=conclusion,
    )
    _assert_channel_progress_notes_match_status(
        start_date=start_date,
        progress_rows_with_notes=progress_rows_with_notes,
    )

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
    _assert_completed_window_not_before_end_date(
        window_status=window_status,
        current_date=current_date,
        end_date=end_date,
    )
    _assert_window_completes_immediately_when_exit_conditions_are_met(
        current_date=current_date,
        end_date=end_date,
        window_status=window_status,
        window_activity=window_activity,
        conclusion=conclusion,
        window_completed=window_completed,
        progress_rows=progress_rows,
        smoke_gate_checklist_completed=smoke_gate_checklist_completed,
        protocol_regression_checklist_completed=protocol_regression_checklist_completed,
        docs_gate_checklist_completed=docs_gate_checklist_completed,
    )
    _assert_completed_window_keeps_all_evidence_checks_completed(
        window_status=window_status,
        smoke_gate_checklist_completed=smoke_gate_checklist_completed,
        protocol_regression_checklist_completed=protocol_regression_checklist_completed,
        docs_gate_checklist_completed=docs_gate_checklist_completed,
    )
    _assert_completed_conclusion_drops_gap_wording(
        window_status=window_status,
        conclusion=conclusion,
    )

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
