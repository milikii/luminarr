from __future__ import annotations

from pathlib import Path
import re


def _extract_window_dates(text: str) -> tuple[str, str]:
    start_match = re.search(r"- 开始日期：(\d{4}-\d{2}-\d{2})", text)
    end_match = re.search(r"- 最早可结束日期：(\d{4}-\d{2}-\d{2})", text)
    assert start_match is not None
    assert end_match is not None
    return start_match.group(1), end_match.group(1)


def _extract_window_title_dates(text: str) -> tuple[str, str]:
    title_match = re.search(
        r"^# Cleanup verification window \((\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})\) \(v\d+\)$",
        text,
        re.MULTILINE,
    )
    assert title_match is not None
    return title_match.group(1), title_match.group(2)


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


def _extract_status_full_suite_snapshot(text: str) -> tuple[str, str]:
    full_suite_match = re.search(r"- tests：`([^`]+)`（`([^`]+)`）", text)
    assert full_suite_match is not None
    return full_suite_match.group(1), full_suite_match.group(2)


def _extract_status_cleanup_service_snapshot(text: str) -> tuple[str, str]:
    cleanup_service_match = re.search(r"- cleanup service tests：`([^`]+)`（`([^`]+)`）", text)
    assert cleanup_service_match is not None
    return cleanup_service_match.group(1), cleanup_service_match.group(2)


def _extract_status_compile_check_snapshot(text: str) -> tuple[str, str]:
    compile_check_match = re.search(r"- compile check：`([^`]+)`（`([^`]+)`）", text)
    assert compile_check_match is not None
    return compile_check_match.group(1), compile_check_match.group(2)


def _extract_status_docs_consistency_snapshot(text: str) -> tuple[str, str]:
    docs_consistency_match = re.search(r"- docs consistency check：`([^`]+)`（`([^`]+)`）", text)
    assert docs_consistency_match is not None
    return docs_consistency_match.group(1), docs_consistency_match.group(2)


def test_cleanup_verification_window_docs_stay_in_sync() -> None:
    dockerfile_text = Path("Dockerfile").read_text(encoding="utf-8")
    docker_compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    dockerignore_text = Path(".dockerignore").read_text(encoding="utf-8")
    readme_text = Path("README.md").read_text(encoding="utf-8")
    agents_text = Path("AGENTS.md").read_text(encoding="utf-8")
    decisions_text = Path("docs/DECISIONS.md").read_text(encoding="utf-8")
    index_text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    architecture_text = Path("docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    getting_started_text = Path("docs/GETTING_STARTED.md").read_text(encoding="utf-8")
    env_example_text = Path(".env.example").read_text(encoding="utf-8")
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    next_step_text = Path("docs/NEXT_STEP.md").read_text(encoding="utf-8")
    status_text = Path("docs/STATUS.md").read_text(encoding="utf-8")
    window_text = Path("docs/CLEANUP_VERIFICATION_WINDOW.md").read_text(encoding="utf-8")

    title_start_date, title_end_date = _extract_window_title_dates(window_text)
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
    docs_gate_date, docs_gate_result, docs_gate_command = _extract_verification_evidence(
        window_text,
        "最近一次 verification docs gate",
    )
    window_status = _extract_window_status(window_text)
    full_suite_result, full_suite_command = _extract_status_full_suite_snapshot(status_text)
    cleanup_service_result, cleanup_service_command = _extract_status_cleanup_service_snapshot(status_text)
    compile_check_result, compile_check_command = _extract_status_compile_check_snapshot(status_text)
    docs_consistency_result, docs_consistency_command = _extract_status_docs_consistency_snapshot(status_text)

    assert title_start_date == start_date
    assert title_end_date == end_date
    assert full_suite_result == "676 passed, 2 skipped"
    assert full_suite_command == ".venv/bin/python -m pytest -q"
    assert cleanup_service_result == "38 passed"
    assert cleanup_service_command == ".venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py"
    assert compile_check_result == "passed"
    assert compile_check_command == "python3 -m compileall app tests"
    assert docs_consistency_result == "passed"
    assert docs_consistency_command == ".venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py"
    assert f"- 窗口活性快照：{window_activity}" in status_text
    assert f"- 当前状态快照：{window_status}" in status_text
    assert f"- 当前结论快照：{current_conclusion}" in status_text
    assert f"- four-channel cleanup smoke tests：`{smoke_gate_result}`（{smoke_gate_date}，`{smoke_gate_command}`）" in status_text
    assert (
        f"- focused cleanup tests：`{focused_cleanup_result}`（{focused_cleanup_date}，"
        f"`{focused_cleanup_command}`）"
    ) in status_text
    assert (
        f"- cleanup verification docs gate：`{docs_gate_result}`（{docs_gate_date}，"
        f"`{docs_gate_command}`）"
    ) in status_text

    for text in (next_step_text, status_text):
        assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in text
        assert "verification docs gate" in text
        assert "真实私聊 smoke" in text
        if text is next_step_text:
            assert "`tests/test_cleanup_cross_channel_smoke.py`" in text
            assert "cleanup 执行失败" in text
            assert "event_type=cleanup.failed" in text
            assert "lookup_task_ref/task_id/task_hash" in text
            assert "task_id/task_hash + source + target" in text
            assert "Current goal" in text
            assert "Only do" in text
            assert "Do not do" in text
            assert "Done when" in text
            assert "After this step" in text
            assert "bring-up 入口稳定" in text
            assert "pt_min_seed_hours" in text
            assert "只记录风险，不扩 cleanup 行为" in text
        if text is status_text:
            assert "four-channel cleanup smoke tests" in text
            assert "当前结论" in text
            assert "窗口活性" in text
            assert "focused cleanup tests" in text
            assert "Knowledge entrypoints" in text
            assert "What is implemented now" in text
            assert "Main risks and gaps" in text
            assert "Latest verification" in text
            assert "PT 做种 guardrail 评估已记录到 `docs/CLEANUP_VERIFICATION_WINDOW.md`" in text
            assert "pt_min_seed_hours" in text
            assert "job_event` 关联查询失败" in text
            assert "缺结构化 `source_path/target_path`" in text

    assert "docs/INDEX.md" in readme_text
    assert "docs/GETTING_STARTED.md" in readme_text
    assert "docs/ARCHITECTURE.md" in readme_text
    assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in readme_text
    assert "docs/STATUS.md" in readme_text
    assert ".env.example" in readme_text
    assert "Makefile" in readme_text
    assert "docker-compose.yml" in readme_text
    assert "Dockerfile" in readme_text
    assert "context_token" in readme_text
    assert "pt_min_seed_hours" in readme_text
    assert ".ass" in readme_text
    assert "独立后台下载完成轮询" in readme_text
    assert "job_event` 关联查询失败" in readme_text
    assert "缺结构化 `source_path/target_path`" in readme_text
    assert "context_token" in decisions_text
    assert "pt_min_seed_hours" in decisions_text
    assert ".ass" in decisions_text
    assert "docs/CLEANUP_VERIFICATION_WINDOW.md" in decisions_text
    assert "docs/STATUS.md" in decisions_text
    assert "docs/INDEX.md" in agents_text
    assert "docs/ARCHITECTURE.md" in agents_text
    assert "docs/NEXT_STEP.md" in agents_text
    assert "docs/DECISIONS.md" in agents_text
    assert "README.md" in index_text
    assert "docs/GETTING_STARTED.md" in index_text
    assert "docs/ARCHITECTURE.md" in index_text
    assert "AGENTS.md" in index_text
    assert "Makefile" in index_text
    assert "app/main.py" in architecture_text
    assert "app/bot/private_chat_runtime.py" in architecture_text
    assert "app/services/" in architecture_text
    assert "app/db/" in architecture_text
    assert ".env.example" in getting_started_text
    assert "Makefile" in getting_started_text
    assert "make run" in getting_started_text
    assert ".venv/bin/python -m app.main" in getting_started_text
    assert "docker compose up -d" in getting_started_text
    assert "Dockerfile" in getting_started_text
    assert "docker-compose.yml" in getting_started_text
    assert "TELEGRAM_BOT_TOKEN=" in env_example_text
    assert "PROWLARR_BASE_URL=" in env_example_text
    assert "TRANSMISSION_BASE_URL=" in env_example_text
    assert "LIBRARY_TARGET_DIR=" in env_example_text
    assert "SHARED_MEDIA_ROOT=" in env_example_text
    assert "test-cleanup:" in makefile_text
    assert "test-docs:" in makefile_text
    assert "compile:" in makefile_text
    assert "run:" in makefile_text
    assert "docker-build:" in makefile_text
    assert "docker-up:" in makefile_text
    assert "python:3.12-slim" in dockerfile_text
    assert "python\", \"-m\", \"app.main" in dockerfile_text
    assert "build:" in docker_compose_text
    assert "env_file:" in docker_compose_text
    assert "SHARED_MEDIA_ROOT" in docker_compose_text
    assert ".venv" in dockerignore_text
    assert "logs" in dockerignore_text

    window_progress_rows = re.findall(
        r"\| (Telegram|personal WeChat|Feishu|WeCom) \| (待验证|已完成) \| ([0-9-]+|-) \|",
        window_text,
    )
    status_progress_rows = re.findall(
        r"\| (Telegram|personal WeChat|Feishu|WeCom) \| (待验证|已完成) \| ([0-9-]+|-) \|",
        status_text,
    )
    assert re.search(r"^\| 渠道 \| 状态 \| 最近一次日期 \| 备注 \|$", window_text, re.MULTILINE) is not None
    assert re.search(r"^\| 渠道 \| 状态 \| 最近一次日期 \| 备注 \|$", status_text, re.MULTILINE) is None
    assert "待补真实私聊 smoke 记录" not in status_text
    assert re.search(r"^- 当前 cleanup 协议观察：", status_text, re.MULTILINE) is None
    assert "## PT 做种 guardrail 评估" in window_text
    assert "pt_min_seed_hours" in window_text
    assert "做种" in window_text
    assert "只记录风险，不扩 cleanup 行为" in window_text
    assert len(window_progress_rows) == 4
    assert status_progress_rows == window_progress_rows
