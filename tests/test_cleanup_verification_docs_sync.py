from __future__ import annotations

import io
from pathlib import Path
import subprocess

import pytest

from app.bot.cleanup_smoke_logging import build_cleanup_private_chat_smoke_log_line
from app.maintenance.cleanup_verification_docs import (
    CleanupVerificationDocsSyncError,
    SNAPSHOT_SPECS,
    SnapshotRun,
    _has_running_luminarr_process,
    _read_windows_env_values,
    _run_env_readiness_snapshot,
    _run_local_smoke_evidence_snapshot,
    _run_runtime_process_snapshot,
    _run_telegram_bot_api_snapshot,
    parse_pytest_result,
    update_status_text,
    update_window_text,
)


def test_parse_pytest_result_strips_duration_suffix() -> None:
    stdout = "...\n724 passed, 2 skipped in 33.21s\n"

    assert parse_pytest_result(stdout) == "724 passed, 2 skipped"


def test_parse_pytest_result_strips_duration_suffix_with_clock_format() -> None:
    stdout = "...\n384 passed in 109.83s (0:01:49)\n"

    assert parse_pytest_result(stdout) == "384 passed"


def test_parse_pytest_result_raises_for_unexpected_summary() -> None:
    with pytest.raises(CleanupVerificationDocsSyncError):
        parse_pytest_result("no useful summary here\n")


def test_update_status_text_replaces_date_first_and_result_first_entries() -> None:
    original = (
        "## Latest verification\n\n"
        "- tests：2026-04-10，`700 passed`（`.venv/bin/python -m pytest -q`）\n"
        "- four-channel cleanup smoke tests：`370 passed`（2026-04-10，"
        "`old smoke command`）\n"
    )
    runs = [
        SnapshotRun(
            spec=SNAPSHOT_SPECS["full_suite"],
            date_text="2026-04-11",
            result_text="724 passed, 2 skipped",
        ),
        SnapshotRun(
            spec=SNAPSHOT_SPECS["smoke_gate"],
            date_text="2026-04-11",
            result_text="376 passed",
        ),
    ]

    updated = update_status_text(original, runs)

    assert "- tests：2026-04-11，`724 passed, 2 skipped`（`.venv/bin/python -m pytest -q`）" in updated
    assert (
        "- four-channel cleanup smoke tests：`376 passed`"
        "（2026-04-11，`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）"
    ) in updated


def test_update_window_text_replaces_verification_evidence_entry() -> None:
    original = (
        "## Verification evidence\n\n"
        "- 最近一次聚合 smoke gate：2026-04-10，`370 passed`（`old smoke command`）\n"
    )
    runs = [
        SnapshotRun(
            spec=SNAPSHOT_SPECS["smoke_gate"],
            date_text="2026-04-11",
            result_text="376 passed",
        ),
    ]

    updated = update_window_text(original, runs)

    assert (
        "- 最近一次聚合 smoke gate：2026-04-11，`376 passed`"
        "（`.venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py`）"
    ) in updated


def test_update_status_text_replaces_custom_snapshot_entries() -> None:
    original = (
        "## Latest verification\n\n"
        "- env readiness snapshot：`old result`（2026-04-10，`old env command`）\n"
        "- telegram bot api snapshot：`old bot result`（2026-04-10，`old bot command`）\n"
        "- local smoke evidence snapshot：`old evidence`（2026-04-10，`old evidence command`）\n"
        "- runtime process snapshot：`old process result`（2026-04-10，`old process command`）\n"
    )
    runs = [
        SnapshotRun(
            spec=SNAPSHOT_SPECS["env_readiness"],
            date_text="2026-04-11",
            result_text="local runtime/import env ready; four-channel cleanup smoke env incomplete",
        ),
        SnapshotRun(
            spec=SNAPSHOT_SPECS["telegram_bot_api"],
            date_text="2026-04-11",
            result_text="telegram bot api ready",
        ),
        SnapshotRun(
            spec=SNAPSHOT_SPECS["local_smoke_evidence"],
            date_text="2026-04-11",
            result_text="no in-window cleanup smoke evidence in repo; missing channels: telegram,personal_wechat,feishu,wecom",
        ),
        SnapshotRun(
            spec=SNAPSHOT_SPECS["runtime_process"],
            date_text="2026-04-11",
            result_text="no luminarr process running",
        ),
    ]

    updated = update_status_text(original, runs)

    assert "env readiness snapshot：`local runtime/import env ready; four-channel cleanup smoke env incomplete`" in updated
    assert "source ~/.bashrc >/dev/null 2>&1" in updated
    assert "cmd.exe','/c','set" in updated
    assert "env_path=Path('.env')" in updated
    assert "- telegram bot api snapshot：`telegram bot api ready`" in updated
    assert "api.telegram.org/bot" in updated
    assert "getMe" in updated
    assert "- local smoke evidence snapshot：`no in-window cleanup smoke evidence in repo; missing channels: telegram,personal_wechat,feishu,wecom`" in updated
    assert "sqlite3 -header -column data/luminarr.db" in updated
    assert 'rg -n "\\[cleanup 私聊 smoke\\]" logs' in updated
    assert "- runtime process snapshot：`no luminarr process running`" in updated
    assert "proc_root=Path('/proc')" in updated


def test_update_status_text_migrates_legacy_env_snapshot_label() -> None:
    original = (
        "## Latest verification\n\n"
        "- current shell env readiness check：`old result`（2026-04-10，`old env command`）\n"
    )
    runs = [
        SnapshotRun(
            spec=SNAPSHOT_SPECS["env_readiness"],
            date_text="2026-04-11",
            result_text="local runtime/import env ready; four-channel cleanup smoke env incomplete",
        ),
    ]

    updated = update_status_text(original, runs)

    assert (
        "- env readiness snapshot：`local runtime/import env ready; four-channel cleanup smoke env incomplete`"
    ) in updated


def test_update_window_text_replaces_custom_snapshot_entries() -> None:
    original = (
        "## Verification evidence\n\n"
        "- 当前环境就绪快照：2026-04-10，`old env result`（`old env command`）\n"
        "- 当前 Telegram Bot API 就绪快照：2026-04-10，`old bot result`（`old bot command`）\n"
        "- 当前仓库证据快照：2026-04-10，`old evidence result`（`old evidence command`）\n"
        "- 当前运行进程快照：2026-04-10，`old process result`（`old process command`）\n"
    )
    runs = [
        SnapshotRun(
            spec=SNAPSHOT_SPECS["env_readiness"],
            date_text="2026-04-11",
            result_text="local runtime/import env ready; four-channel cleanup smoke env incomplete",
        ),
        SnapshotRun(
            spec=SNAPSHOT_SPECS["telegram_bot_api"],
            date_text="2026-04-11",
            result_text="telegram bot api ready",
        ),
        SnapshotRun(
            spec=SNAPSHOT_SPECS["local_smoke_evidence"],
            date_text="2026-04-11",
            result_text="no in-window cleanup smoke evidence in repo; missing channels: telegram,personal_wechat,feishu,wecom",
        ),
        SnapshotRun(
            spec=SNAPSHOT_SPECS["runtime_process"],
            date_text="2026-04-11",
            result_text="no luminarr process running",
        ),
    ]

    updated = update_window_text(original, runs)

    assert (
        "- 当前环境就绪快照：2026-04-11，"
        "`local runtime/import env ready; four-channel cleanup smoke env incomplete`"
    ) in updated
    assert "source ~/.bashrc >/dev/null 2>&1" in updated
    assert "cmd.exe','/c','set" in updated
    assert "env_path=Path('.env')" in updated
    assert "- 当前 Telegram Bot API 就绪快照：2026-04-11，`telegram bot api ready`" in updated
    assert "api.telegram.org/bot" in updated
    assert "getMe" in updated
    assert "- 当前仓库证据快照：2026-04-11，`no in-window cleanup smoke evidence in repo; missing channels: telegram,personal_wechat,feishu,wecom`" in updated
    assert "sqlite3 -header -column data/luminarr.db" in updated
    assert 'rg -n "\\[cleanup 私聊 smoke\\]" logs' in updated
    assert "- 当前运行进程快照：2026-04-11，`no luminarr process running`" in updated
    assert "proc_root=Path('/proc')" in updated


def test_run_env_readiness_snapshot_returns_missing_when_env_is_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in (
        "TELEGRAM_BOT_TOKEN",
        "PROWLARR_BASE_URL",
        "PROWLARR_API_KEY",
        "TRANSMISSION_BASE_URL",
        "EMBY_BASE_URL",
        "EMBY_API_KEY",
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
        "FEISHU_ENCRYPT_KEY",
        "WECOM_TOKEN",
        "WECOM_ENCODING_AES_KEY",
        "WECOM_RECEIVE_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    assert _run_env_readiness_snapshot(tmp_path) == "missing local runtime env"


def test_read_windows_env_values_tolerates_non_utf8_cmd_output(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = "用作当前目录不受支持。\r\nTELEGRAM_BOT_TOKEN=token\r\n".encode("gbk")

    monkeypatch.setattr(
        "app.maintenance.cleanup_verification_docs.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=stdout, stderr=b""),
    )

    assert _read_windows_env_values()["TELEGRAM_BOT_TOKEN"] == "token"


def test_run_env_readiness_snapshot_reads_local_env_file_when_process_env_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for key in (
        "TELEGRAM_BOT_TOKEN",
        "PROWLARR_BASE_URL",
        "PROWLARR_API_KEY",
        "TRANSMISSION_BASE_URL",
        "EMBY_BASE_URL",
        "EMBY_API_KEY",
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
        "FEISHU_ENCRYPT_KEY",
        "WECOM_TOKEN",
        "WECOM_ENCODING_AES_KEY",
        "WECOM_RECEIVE_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "TELEGRAM_BOT_TOKEN=token",
                "PROWLARR_BASE_URL=http://127.0.0.1:9696",
                "PROWLARR_API_KEY=prowlarr-key",
                "TRANSMISSION_BASE_URL=http://127.0.0.1:19091",
                "EMBY_BASE_URL=http://127.0.0.1:18096",
                "EMBY_API_KEY=emby-key",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        _run_env_readiness_snapshot(tmp_path)
        == "local runtime/import env ready; four-channel cleanup smoke env incomplete"
    )


def test_run_telegram_bot_api_snapshot_returns_missing_when_token_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    assert _run_telegram_bot_api_snapshot(tmp_path) == "telegram bot token missing"


def test_run_telegram_bot_api_snapshot_reads_env_file_and_returns_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=test-token\n", encoding="utf-8")

    class _FakeResponse(io.BytesIO):
        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.close()

    def _fake_urlopen(url: str, timeout: int):
        assert "test-token" in url
        assert timeout == 5
        return _FakeResponse(b'{"ok": true, "result": {"username": "demo_bot"}}')

    monkeypatch.setattr("app.maintenance.cleanup_verification_docs.urllib.request.urlopen", _fake_urlopen)

    assert _run_telegram_bot_api_snapshot(tmp_path) == "telegram bot api ready"


def test_run_telegram_bot_api_snapshot_returns_rejected_when_api_says_not_ok(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    class _FakeResponse(io.BytesIO):
        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.close()

    monkeypatch.setattr(
        "app.maintenance.cleanup_verification_docs.urllib.request.urlopen",
        lambda url, timeout: _FakeResponse(b'{"ok": false, "description": "unauthorized"}'),
    )

    assert _run_telegram_bot_api_snapshot(tmp_path) == "telegram bot api rejected token"


def test_run_local_smoke_evidence_snapshot_returns_missing_when_repo_has_no_window_evidence(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "CLEANUP_VERIFICATION_WINDOW.md").write_text(
        "# Cleanup verification window (2026-04-05 to 2026-04-12) (v1)\n\n"
        "- 开始日期：2026-04-05\n"
        "- 最早可结束日期：2026-04-12\n",
        encoding="utf-8",
    )
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    old_log = logs_dir / "run_2026-04-12_132239.log"
    old_log.write_text("not a cleanup smoke log\n", encoding="utf-8")

    assert _run_local_smoke_evidence_snapshot(tmp_path) == "no in-window cleanup smoke evidence in repo; missing channels: telegram,personal_wechat,feishu,wecom"


def test_run_local_smoke_evidence_snapshot_returns_missing_when_log_date_is_outside_window(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "CLEANUP_VERIFICATION_WINDOW.md").write_text(
        "# Cleanup verification window (2026-04-05 to 2026-04-12) (v1)\n\n"
        "- 开始日期：2026-04-05\n"
        "- 最早可结束日期：2026-04-12\n",
        encoding="utf-8",
    )
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    smoke_log_line = build_cleanup_private_chat_smoke_log_line(
        channel="telegram",
        query="cleanup inspect abc123",
        reply_text="已完成检查",
        chat_id=1,
        user_id=1,
        date_text="2026-04-03",
    )
    assert smoke_log_line is not None
    (logs_dir / "run_2026-04-12.log").write_text(f"{smoke_log_line}\n", encoding="utf-8")

    assert _run_local_smoke_evidence_snapshot(tmp_path) == "no in-window cleanup smoke evidence in repo; missing channels: telegram,personal_wechat,feishu,wecom"


def test_run_local_smoke_evidence_snapshot_returns_found_when_repo_has_window_cleanup_smoke_log(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "CLEANUP_VERIFICATION_WINDOW.md").write_text(
        "# Cleanup verification window (2026-04-05 to 2026-04-12) (v1)\n\n"
        "- 开始日期：2026-04-05\n"
        "- 最早可结束日期：2026-04-12\n",
        encoding="utf-8",
    )
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    smoke_log_line = build_cleanup_private_chat_smoke_log_line(
        channel="telegram",
        query="cleanup inspect abc123",
        reply_text="已完成检查",
        chat_id=1,
        user_id=1,
        date_text="2026-04-06",
    )
    assert smoke_log_line is not None
    (logs_dir / "run.log").write_text(f"{smoke_log_line}\n", encoding="utf-8")

    assert _run_local_smoke_evidence_snapshot(tmp_path) == "found in-window cleanup smoke evidence in repo: telegram; missing channels: personal_wechat,feishu,wecom"


def test_run_local_smoke_evidence_snapshot_returns_all_channels_covered_when_window_has_all_channel_logs(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "CLEANUP_VERIFICATION_WINDOW.md").write_text(
        "# Cleanup verification window (2026-04-05 to 2026-04-12) (v1)\n\n- 开始日期：2026-04-05\n- 最早可结束日期：2026-04-12\n",
        encoding="utf-8",
    )
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    lines = [build_cleanup_private_chat_smoke_log_line(channel=channel, query="cleanup inspect abc123", reply_text="已完成检查", chat_id=1, user_id=1, date_text="2026-04-06") for channel in ("telegram", "personal_wechat", "feishu", "wecom")]
    assert all(line is not None for line in lines)
    (logs_dir / "run.log").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    assert _run_local_smoke_evidence_snapshot(tmp_path) == "found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered"


def test_has_running_luminarr_process_returns_false_when_app_main_is_absent(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    pid_dir = proc_root / "101"
    pid_dir.mkdir()
    (pid_dir / "cmdline").write_bytes(b"/usr/bin/bash\0-l\0")

    assert not _has_running_luminarr_process(proc_root)


def test_has_running_luminarr_process_returns_true_when_app_main_process_exists(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    pid_dir = proc_root / "202"
    pid_dir.mkdir()
    (pid_dir / "cmdline").write_bytes(b"/usr/bin/python3\0-m\0app.main\0")

    assert _has_running_luminarr_process(proc_root)


def test_run_runtime_process_snapshot_returns_no_process_when_proc_has_no_app_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.maintenance.cleanup_verification_docs._has_running_luminarr_process", lambda _: False)

    assert _run_runtime_process_snapshot(Path(".")) == "no luminarr process running"


def test_run_runtime_process_snapshot_returns_running_when_proc_has_app_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.maintenance.cleanup_verification_docs._has_running_luminarr_process", lambda _: True)

    assert _run_runtime_process_snapshot(Path(".")) == "luminarr process running"


def test_update_status_text_raises_when_label_is_missing() -> None:
    run = SnapshotRun(
        spec=SNAPSHOT_SPECS["docs_consistency"],
        date_text="2026-04-11",
        result_text="passed",
    )

    with pytest.raises(CleanupVerificationDocsSyncError):
        update_status_text("## Latest verification\n", [run])
