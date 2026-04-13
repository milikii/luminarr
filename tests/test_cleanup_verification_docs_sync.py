from __future__ import annotations

import io
from pathlib import Path
import subprocess
import urllib.error

import pytest

from app.bot.cleanup_smoke_logging import build_cleanup_private_chat_smoke_log_line
from app.maintenance.cleanup_verification_docs import (
    CleanupVerificationDocsSyncError,
    SNAPSHOT_SPECS,
    SnapshotRun,
    _collect_in_window_cleanup_smoke_channel_dates,
    _has_running_luminarr_process,
    _read_current_shell_env_values,
    _read_windows_env_values,
    _replace_window_channel_progress_table,
    _run_env_readiness_snapshot,
    _run_local_smoke_evidence_snapshot,
    _run_runtime_process_snapshot,
    _run_telegram_bot_api_snapshot,
    parse_pytest_result,
    sync_documents,
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
            result_text="local runtime/import env ready; four-channel cleanup smoke env incomplete; missing channels: feishu,wecom; personal_wechat login state not checked",
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

    assert "env readiness snapshot：`local runtime/import env ready; four-channel cleanup smoke env incomplete; missing channels: feishu,wecom; personal_wechat login state not checked`" in updated
    assert "source ~/.bashrc >/dev/null 2>&1" in updated
    assert "os.getenv(k,\\\"\\\").strip().strip" in updated
    assert "rows=dict(line.split('=', 1)" in updated
    assert "lookup.get(k.lower(), '')" in updated
    assert "env_path=Path('.env')" in updated
    assert "value.strip().strip" in updated
    assert "- telegram bot api snapshot：`telegram bot api ready`" in updated
    assert "api.telegram.org/bot" in updated
    assert "getMe" in updated
    assert "os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip" in updated
    assert "line.partition('=')[0].strip().lower() == 'telegram_bot_token'" in updated
    assert "line.partition('=')[2].strip().strip" in updated
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
            result_text="local runtime/import env ready; four-channel cleanup smoke env incomplete; missing channels: feishu,wecom; personal_wechat login state not checked",
        ),
    ]

    updated = update_status_text(original, runs)

    assert (
        "- env readiness snapshot：`local runtime/import env ready; four-channel cleanup smoke env incomplete; missing channels: feishu,wecom; personal_wechat login state not checked`"
    ) in updated
    assert "os.getenv(k,\\\"\\\").strip().strip" in updated
    assert "rows=dict(line.split('=', 1)" in updated
    assert "lookup.get(k.lower(), '')" in updated


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
            result_text="local runtime/import env ready; four-channel cleanup smoke env incomplete; missing channels: feishu,wecom; personal_wechat login state not checked",
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
        "`local runtime/import env ready; four-channel cleanup smoke env incomplete; missing channels: feishu,wecom; personal_wechat login state not checked`"
    ) in updated
    assert "source ~/.bashrc >/dev/null 2>&1" in updated
    assert "cmd.exe','/c','set" in updated
    assert "env_path=Path('.env')" in updated
    assert "value.strip().strip" in updated
    assert "strip('\\\"\\'')" in updated
    assert "- 当前 Telegram Bot API 就绪快照：2026-04-11，`telegram bot api ready`" in updated
    assert "api.telegram.org/bot" in updated
    assert "getMe" in updated
    assert "os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip" in updated
    assert "token=os.getenv('TELEGRAM_BOT_TOKEN','').strip().strip('\\\"\\'')" in updated
    assert "line.partition('=')[0].strip().lower() == 'telegram_bot_token'" in updated
    assert "line.partition('=')[2].strip().strip" in updated
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


def test_read_current_shell_env_values_strips_matching_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", '"token"')

    assert _read_current_shell_env_values()["TELEGRAM_BOT_TOKEN"] == "token"


def test_read_windows_env_values_tolerates_non_utf8_cmd_output(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = "用作当前目录不受支持。\r\nTELEGRAM_BOT_TOKEN=token\r\n".encode("gbk")

    monkeypatch.setattr(
        "app.maintenance.cleanup_verification_docs.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=stdout, stderr=b""),
    )

    assert _read_windows_env_values()["TELEGRAM_BOT_TOKEN"] == "token"


def test_read_windows_env_values_treats_keys_case_insensitively(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = b"telegram_bot_token=token\r\n"

    monkeypatch.setattr(
        "app.maintenance.cleanup_verification_docs.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=stdout, stderr=b""),
    )

    assert _read_windows_env_values()["TELEGRAM_BOT_TOKEN"] == "token"


def test_read_windows_env_values_strips_matching_quotes_from_values(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = b'TELEGRAM_BOT_TOKEN="token"\r\n'

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
        == "local runtime/import env ready; four-channel cleanup smoke env incomplete; missing channels: feishu,wecom; personal_wechat login state not checked"
    )


def test_run_env_readiness_snapshot_lists_only_missing_channel_groups(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in ("TELEGRAM_BOT_TOKEN", "PROWLARR_BASE_URL", "PROWLARR_API_KEY", "TRANSMISSION_BASE_URL", "EMBY_BASE_URL", "EMBY_API_KEY", "FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_ENCRYPT_KEY", "WECOM_TOKEN", "WECOM_ENCODING_AES_KEY", "WECOM_RECEIVE_ID"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=token\nPROWLARR_BASE_URL=http://127.0.0.1:9696\nPROWLARR_API_KEY=prowlarr-key\nTRANSMISSION_BASE_URL=http://127.0.0.1:19091\nEMBY_BASE_URL=http://127.0.0.1:18096\nEMBY_API_KEY=emby-key\nFEISHU_APP_ID=id\nFEISHU_APP_SECRET=secret\nFEISHU_ENCRYPT_KEY=key\n", encoding="utf-8")
    assert _run_env_readiness_snapshot(tmp_path) == "local runtime/import env ready; four-channel cleanup smoke env incomplete; missing channels: wecom; personal_wechat login state not checked"


def test_run_telegram_bot_api_snapshot_reads_quoted_env_file_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    (tmp_path / ".env").write_text('TELEGRAM_BOT_TOKEN="test-token"\n', encoding="utf-8")

    class _FakeResponse(io.BytesIO):
        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.close()

    def _fake_urlopen(url: str, timeout: int):
        assert '"test-token"' not in url
        assert "test-token" in url
        assert timeout == 5
        return _FakeResponse(b'{"ok": true, "result": {"username": "demo_bot"}}')

    monkeypatch.setattr("app.maintenance.cleanup_verification_docs.urllib.request.urlopen", _fake_urlopen)

    assert _run_telegram_bot_api_snapshot(tmp_path) == "telegram bot api ready"


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


def test_run_telegram_bot_api_snapshot_treats_http_unauthorized_as_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(
        "app.maintenance.cleanup_verification_docs.urllib.request.urlopen",
        lambda url, timeout: (_ for _ in ()).throw(
            urllib.error.HTTPError(url, 401, "Unauthorized", hdrs=None, fp=None)
        ),
    )

    assert _run_telegram_bot_api_snapshot(tmp_path) == "telegram bot api rejected token"


def test_run_telegram_bot_api_snapshot_treats_urlerror_as_unreachable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr("app.maintenance.cleanup_verification_docs.urllib.request.urlopen", lambda url, timeout: (_ for _ in ()).throw(urllib.error.URLError("offline")))
    assert _run_telegram_bot_api_snapshot(tmp_path) == "telegram bot api unreachable"


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


def test_collect_in_window_cleanup_smoke_channel_dates_keeps_latest_date_per_channel(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "CLEANUP_VERIFICATION_WINDOW.md").write_text(
        "# Cleanup verification window (2026-04-05 to 2026-04-12) (v1)\n\n- 开始日期：2026-04-05\n- 最早可结束日期：2026-04-12\n",
        encoding="utf-8",
    )
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    lines = [
        build_cleanup_private_chat_smoke_log_line(channel="telegram", query="cleanup inspect abc123", reply_text="已完成检查", chat_id=1, user_id=1, date_text="2026-04-06"),
        build_cleanup_private_chat_smoke_log_line(channel="telegram", query="cleanup inspect abc123", reply_text="已完成检查", chat_id=1, user_id=1, date_text="2026-04-08"),
        build_cleanup_private_chat_smoke_log_line(channel="feishu", query="cleanup inspect abc123", reply_text="已完成检查", chat_id=1, user_id=1, date_text="2026-04-05"),
        build_cleanup_private_chat_smoke_log_line(channel="wecom", query="cleanup inspect abc123", reply_text="已完成检查", chat_id=1, user_id=1, date_text="2026-04-03"),
    ]
    assert all(line is not None for line in lines)
    (logs_dir / "run.log").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    assert _collect_in_window_cleanup_smoke_channel_dates(tmp_path) == {"telegram": "2026-04-08", "feishu": "2026-04-05"}


def test_collect_in_window_cleanup_smoke_channel_dates_accepts_post_window_evidence_until_today(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "CLEANUP_VERIFICATION_WINDOW.md").write_text(
        "# Cleanup verification window (2026-04-05 to 2026-04-12) (v1)\n\n- 开始日期：2026-04-05\n- 最早可结束日期：2026-04-12\n",
        encoding="utf-8",
    )
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    line = build_cleanup_private_chat_smoke_log_line(
        channel="telegram",
        query="cleanup inspect abc123",
        reply_text="已完成检查",
        chat_id=1,
        user_id=1,
        date_text="2026-04-13",
    )
    assert line is not None
    (logs_dir / "run.log").write_text(f"{line}\n", encoding="utf-8")
    monkeypatch.setattr("app.maintenance.cleanup_verification_docs.datetime", type("FrozenDateTime", (), {"now": staticmethod(lambda tz=None: __import__("datetime").datetime(2026, 4, 13, tzinfo=tz))}))

    assert _collect_in_window_cleanup_smoke_channel_dates(tmp_path) == {"telegram": "2026-04-13"}


def test_replace_window_channel_progress_table_updates_completed_and_pending_rows() -> None:
    original = (
        "## Channel progress\n\n"
        "| 渠道 | 状态 | 最近一次日期 | 备注 |\n"
        "| --- | --- | --- | --- |\n"
        "| Telegram | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n"
        "| personal WeChat | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n"
        "| Feishu | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n"
        "| WeCom | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n"
        "\n## Verification evidence\n\n"
        "- keep me\n"
    )

    updated = _replace_window_channel_progress_table(
        original,
        channel_dates={"telegram": "2026-04-08", "feishu": "2026-04-06"},
        window_start_date="2026-04-05",
    )

    assert "| Telegram | 已完成 | 2026-04-08 | 2026-04-08 已完成真实私聊 smoke |" in updated
    assert "| personal WeChat | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |" in updated
    assert "| Feishu | 已完成 | 2026-04-06 | 2026-04-06 已完成真实私聊 smoke |" in updated
    assert "| WeCom | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |" in updated
    assert "\n## Verification evidence" in updated


def test_sync_documents_keeps_window_sections_when_rewriting_channel_progress(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    status_file = docs_dir / "STATUS.md"
    status_file.write_text("## Latest verification\n\n- local smoke evidence snapshot：`old evidence`（2026-04-10，`old evidence command`）\n", encoding="utf-8")
    window_file = docs_dir / "CLEANUP_VERIFICATION_WINDOW.md"
    window_file.write_text("# Cleanup verification window (2026-04-05 to 2026-04-12) (v1)\n\n- 开始日期：2026-04-05\n- 最早可结束日期：2026-04-12\n\n## Channel progress\n\n| 渠道 | 状态 | 最近一次日期 | 备注 |\n| --- | --- | --- | --- |\n| Telegram | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| personal WeChat | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| Feishu | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| WeCom | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n\n## Verification evidence\n\n- 当前仓库证据快照：2026-04-10，`old evidence result`（`old evidence command`）\n\n## PT 做种 guardrail 评估\n\n- keep me\n\n## Update rule\n\n- keep me too\n", encoding="utf-8")
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    line = build_cleanup_private_chat_smoke_log_line(channel="telegram", query="cleanup inspect abc123", reply_text="已完成检查", chat_id=1, user_id=1, date_text="2026-04-06")
    assert line is not None
    (logs_dir / "run.log").write_text(f"{line}\n", encoding="utf-8")
    monkeypatch.setattr("app.maintenance.cleanup_verification_docs.run_snapshot", lambda spec, cwd: SnapshotRun(spec=spec, date_text="2026-04-11", result_text="found in-window cleanup smoke evidence in repo: telegram; missing channels: personal_wechat,feishu,wecom"))

    sync_documents(status_file=status_file, window_file=window_file, snapshot_keys=["local_smoke_evidence"], cwd=tmp_path)

    updated = window_file.read_text(encoding="utf-8")
    assert "| Telegram | 已完成 | 2026-04-06 | 2026-04-06 已完成真实私聊 smoke |" in updated
    assert "## Verification evidence" in updated and "## PT 做种 guardrail 评估" in updated and "## Update rule" in updated


def test_sync_documents_keeps_fixed_channel_order_when_logs_are_out_of_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "STATUS.md").write_text("## Latest verification\n\n- local smoke evidence snapshot：`old evidence`（2026-04-10，`old evidence command`）\n", encoding="utf-8")
    window_file = docs_dir / "CLEANUP_VERIFICATION_WINDOW.md"
    window_file.write_text("# Cleanup verification window (2026-04-05 to 2026-04-12) (v1)\n\n- 开始日期：2026-04-05\n- 最早可结束日期：2026-04-12\n\n## Channel progress\n\n| 渠道 | 状态 | 最近一次日期 | 备注 |\n| --- | --- | --- | --- |\n| Telegram | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| personal WeChat | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| Feishu | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| WeCom | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n\n## Verification evidence\n\n- 当前仓库证据快照：2026-04-10，`old evidence result`（`old evidence command`）\n", encoding="utf-8")
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    lines = [build_cleanup_private_chat_smoke_log_line(channel=channel, query="cleanup inspect abc123", reply_text="已完成检查", chat_id=1, user_id=1, date_text="2026-04-06") for channel in ("wecom", "feishu", "personal_wechat", "telegram")]
    assert all(line is not None for line in lines)
    (logs_dir / "run.log").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    monkeypatch.setattr("app.maintenance.cleanup_verification_docs.run_snapshot", lambda spec, cwd: SnapshotRun(spec=spec, date_text="2026-04-11", result_text="found in-window cleanup smoke evidence in repo: telegram,personal_wechat,feishu,wecom; all channels covered"))

    sync_documents(status_file=docs_dir / "STATUS.md", window_file=window_file, snapshot_keys=["local_smoke_evidence"], cwd=tmp_path)

    updated = window_file.read_text(encoding="utf-8")
    assert updated.index("| Telegram | 已完成 | 2026-04-06 |") < updated.index("| personal WeChat | 已完成 | 2026-04-06 |") < updated.index("| Feishu | 已完成 | 2026-04-06 |") < updated.index("| WeCom | 已完成 | 2026-04-06 |")


def test_sync_documents_keeps_latest_channel_date_when_window_logs_repeat_channel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "STATUS.md").write_text("## Latest verification\n\n- local smoke evidence snapshot：`old evidence`（2026-04-10，`old evidence command`）\n", encoding="utf-8")
    window_file = docs_dir / "CLEANUP_VERIFICATION_WINDOW.md"
    window_file.write_text("# Cleanup verification window (2026-04-05 to 2026-04-12) (v1)\n\n- 开始日期：2026-04-05\n- 最早可结束日期：2026-04-12\n\n## Channel progress\n\n| 渠道 | 状态 | 最近一次日期 | 备注 |\n| --- | --- | --- | --- |\n| Telegram | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| personal WeChat | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| Feishu | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| WeCom | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n\n## Verification evidence\n\n- 当前仓库证据快照：2026-04-10，`old evidence result`（`old evidence command`）\n", encoding="utf-8")
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    lines = [build_cleanup_private_chat_smoke_log_line(channel="telegram", query="cleanup inspect abc123", reply_text="已完成检查", chat_id=1, user_id=1, date_text=date_text) for date_text in ("2026-04-06", "2026-04-08")]
    assert all(line is not None for line in lines)
    (logs_dir / "run.log").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    monkeypatch.setattr("app.maintenance.cleanup_verification_docs.run_snapshot", lambda spec, cwd: SnapshotRun(spec=spec, date_text="2026-04-11", result_text="found in-window cleanup smoke evidence in repo: telegram; missing channels: personal_wechat,feishu,wecom"))

    sync_documents(status_file=docs_dir / "STATUS.md", window_file=window_file, snapshot_keys=["local_smoke_evidence"], cwd=tmp_path)

    assert "| Telegram | 已完成 | 2026-04-08 | 2026-04-08 已完成真实私聊 smoke |" in window_file.read_text(encoding="utf-8")


def test_sync_documents_keeps_pending_channel_anchor_when_only_one_channel_completes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "STATUS.md").write_text("## Latest verification\n\n- local smoke evidence snapshot：`old evidence`（2026-04-10，`old evidence command`）\n", encoding="utf-8")
    window_file = docs_dir / "CLEANUP_VERIFICATION_WINDOW.md"
    window_file.write_text("# Cleanup verification window (2026-04-05 to 2026-04-12) (v1)\n\n- 开始日期：2026-04-05\n- 最早可结束日期：2026-04-12\n\n## Channel progress\n\n| 渠道 | 状态 | 最近一次日期 | 备注 |\n| --- | --- | --- | --- |\n| Telegram | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| personal WeChat | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| Feishu | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n| WeCom | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |\n\n## Verification evidence\n\n- 当前仓库证据快照：2026-04-10，`old evidence result`（`old evidence command`）\n", encoding="utf-8")
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    line = build_cleanup_private_chat_smoke_log_line(channel="telegram", query="cleanup inspect abc123", reply_text="已完成检查", chat_id=1, user_id=1, date_text="2026-04-06")
    assert line is not None
    (logs_dir / "run.log").write_text(f"{line}\n", encoding="utf-8")
    monkeypatch.setattr("app.maintenance.cleanup_verification_docs.run_snapshot", lambda spec, cwd: SnapshotRun(spec=spec, date_text="2026-04-11", result_text="found in-window cleanup smoke evidence in repo: telegram; missing channels: personal_wechat,feishu,wecom"))

    sync_documents(status_file=docs_dir / "STATUS.md", window_file=window_file, snapshot_keys=["local_smoke_evidence"], cwd=tmp_path)

    updated = window_file.read_text(encoding="utf-8")
    assert "| personal WeChat | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |" in updated and "| Feishu | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |" in updated and "| WeCom | 待验证 | - | 2026-04-05 启动验证窗口，待补真实私聊 smoke 记录 |" in updated


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
