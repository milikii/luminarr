from __future__ import annotations

from argparse import ArgumentParser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from app.bot.cleanup_smoke_logging import parse_cleanup_private_chat_smoke_log_line


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class CleanupVerificationDocsSyncError(RuntimeError):
    def __init__(self, message: str, *, fix_hint: str) -> None:
        super().__init__(message)
        self.fix_hint = fix_hint


SnapshotRunner = Callable[[Path], str]


@dataclass(frozen=True, slots=True)
class SnapshotSpec:
    key: str
    result_kind: str
    command: tuple[str, ...] = ()
    command_display: str = ""
    runner: SnapshotRunner | None = None
    status_label: str | None = None
    status_style: str | None = None
    status_aliases: tuple[str, ...] = ()
    window_label: str | None = None


@dataclass(frozen=True, slots=True)
class SnapshotRun:
    spec: SnapshotSpec
    date_text: str
    result_text: str


LOCAL_RUNTIME_ENV_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "PROWLARR_BASE_URL",
    "PROWLARR_API_KEY",
    "TRANSMISSION_BASE_URL",
)

IMPORT_REFRESH_ENV_KEYS = (
    "EMBY_BASE_URL",
    "EMBY_API_KEY",
)

FOUR_CHANNEL_SMOKE_ENV_KEYS = (
    "FEISHU_APP_ID",
    "FEISHU_APP_SECRET",
    "FEISHU_ENCRYPT_KEY",
    "WECOM_TOKEN",
    "WECOM_ENCODING_AES_KEY",
    "WECOM_RECEIVE_ID",
)

REQUIRED_CHANNEL_RUNTIME_ENV_KEYS = (
    *LOCAL_RUNTIME_ENV_KEYS,
    *IMPORT_REFRESH_ENV_KEYS,
    *FOUR_CHANNEL_SMOKE_ENV_KEYS,
)

ENV_READINESS_COMMAND_DISPLAY = (
    "bash -lc 'source ~/.bashrc >/dev/null 2>&1; python3 -c "
    "\"import os; keys=[\\\"TELEGRAM_BOT_TOKEN\\\",\\\"PROWLARR_BASE_URL\\\",\\\"PROWLARR_API_KEY\\\","
    "\\\"TRANSMISSION_BASE_URL\\\",\\\"EMBY_BASE_URL\\\",\\\"EMBY_API_KEY\\\",\\\"FEISHU_APP_ID\\\","
    "\\\"FEISHU_APP_SECRET\\\",\\\"FEISHU_ENCRYPT_KEY\\\",\\\"WECOM_TOKEN\\\",\\\"WECOM_ENCODING_AES_KEY\\\","
    "\\\"WECOM_RECEIVE_ID\\\"]; print(\\\"\\\\n\\\".join(f\\\"{k}=\\\" + "
    "(\\\"set\\\" if os.getenv(k) else \\\"missing\\\") for k in keys))\"' ; "
    "python3 -c \"import subprocess; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY',"
    "'TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET',"
    "'FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; "
    "out=subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').lower(); "
    "print('\\\\n'.join(f'{k}=' + ('set' if f'{k.lower()}=' in out else 'missing') for k in keys))\" ; "
    "python3 -c \"from pathlib import Path; keys=['TELEGRAM_BOT_TOKEN','PROWLARR_BASE_URL','PROWLARR_API_KEY',"
    "'TRANSMISSION_BASE_URL','EMBY_BASE_URL','EMBY_API_KEY','FEISHU_APP_ID','FEISHU_APP_SECRET',"
    "'FEISHU_ENCRYPT_KEY','WECOM_TOKEN','WECOM_ENCODING_AES_KEY','WECOM_RECEIVE_ID']; data={}; "
    "env_path=Path('.env'); text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; "
    "lines=(line.strip() for line in text.splitlines()); "
    "pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); "
    "data.update(((key.removeprefix('export ').strip()), value.strip()) for key, _, value in pairs); "
    "print('\\\\n'.join(f'{k}=' + ('set' if data.get(k, '').strip() else 'missing') for k in keys))\""
)

LOCAL_SMOKE_EVIDENCE_COMMAND_DISPLAY = (
    "sqlite3 -header -column data/luminarr.db "
    "\"select max(created_at) as max_created_at from jobs; "
    "select max(created_at) as max_created_at from job_event; "
    "select max(created_at) as max_created_at, count(*) as rows from telegram_updates;\" ; "
    "rg -n \"\\[cleanup 私聊 smoke\\]\" logs"
)
RUNTIME_PROCESS_COMMAND_DISPLAY = (
    "python3 -c \"from pathlib import Path; proc_root=Path('/proc'); matches=[]; "
    "pid_dirs=sorted((path for path in proc_root.iterdir() if path.is_dir() and path.name.isdigit()), key=lambda path: int(path.name)); "
    "for pid_dir in pid_dirs: "
    " cmdline_path=pid_dir/'cmdline'; "
    " raw=cmdline_path.read_bytes() if cmdline_path.exists() else b''; "
    " tokens=[token.decode('utf-8', errors='ignore') for token in raw.split(b'\\\\0') if token]; "
    " if tokens and 'python' in Path(tokens[0]).name and any(tokens[index] == '-m' and tokens[index + 1] == 'app.main' for index in range(len(tokens) - 1)): "
    "  matches.append(f'{pid_dir.name} ' + ' '.join(tokens)); "
    "print('\\\\n'.join(matches))\""
)
TELEGRAM_BOT_API_COMMAND_DISPLAY = (
    "python3 -c \"import json, os, subprocess, urllib.request; from pathlib import Path; token=os.getenv('TELEGRAM_BOT_TOKEN','').strip(); "
    "env_path=Path('.env'); env_map={}; text=env_path.read_text(encoding='utf-8') if env_path.exists() else ''; "
    "lines=(line.strip() for line in text.splitlines()); "
    "pairs=(line.partition('=') for line in lines if line and not line.startswith('#') and '=' in line); "
    "env_map.update(((key.removeprefix('export ').strip()), value.strip()) for key, _, value in pairs); "
    "token=token or env_map.get('TELEGRAM_BOT_TOKEN','').strip(); "
    "token=token or next((line.partition('=')[2].strip() for line in subprocess.run(['cmd.exe','/c','set'], capture_output=True).stdout.decode('utf-8', errors='ignore').splitlines() if line.startswith('TELEGRAM_BOT_TOKEN=')), ''); "
    "print('telegram bot token missing' if not token else ('telegram bot api ready' if json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=5)).get('ok') else 'telegram bot api rejected token'))\""
)


WINDOWS_ENV_OUTPUT_ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "cp936", "cp950")
EXPECTED_CLEANUP_SMOKE_CHANNELS = ("telegram", "personal_wechat", "feishu", "wecom")


def _read_current_shell_env_values() -> dict[str, str]:
    return {key: os.getenv(key, "").strip() for key in REQUIRED_CHANNEL_RUNTIME_ENV_KEYS}


def _decode_windows_env_output(raw_output: bytes) -> str:
    for encoding in WINDOWS_ENV_OUTPUT_ENCODINGS:
        try:
            return raw_output.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_output.decode("utf-8", errors="ignore")


def _read_windows_env_values() -> dict[str, str]:
    try:
        completed = subprocess.run(
            ("cmd.exe", "/c", "set"),
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return {key: "" for key in REQUIRED_CHANNEL_RUNTIME_ENV_KEYS}
    if completed.returncode != 0:
        return {key: "" for key in REQUIRED_CHANNEL_RUNTIME_ENV_KEYS}
    windows_env_values: dict[str, str] = {}
    stdout_text = _decode_windows_env_output(completed.stdout)
    for raw_line in stdout_text.splitlines():
        if "=" not in raw_line:
            continue
        key, _, value = raw_line.partition("=")
        windows_env_values[key.strip()] = value.strip()
    return {key: windows_env_values.get(key, "").strip() for key in REQUIRED_CHANNEL_RUNTIME_ENV_KEYS}


def _read_env_file_values(cwd: Path) -> dict[str, str]:
    env_file_path = cwd / ".env"
    if not env_file_path.exists():
        return {key: "" for key in REQUIRED_CHANNEL_RUNTIME_ENV_KEYS}
    env_values: dict[str, str] = {}
    for raw_line in env_file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        normalized_key = key.removeprefix("export ").strip()
        env_values[normalized_key] = value.strip()
    return {key: env_values.get(key, "").strip() for key in REQUIRED_CHANNEL_RUNTIME_ENV_KEYS}


def _build_env_status(values: dict[str, str]) -> dict[str, bool]:
    return {key: bool(values.get(key, "").strip()) for key in REQUIRED_CHANNEL_RUNTIME_ENV_KEYS}


def _merge_env_statuses(*statuses: dict[str, bool]) -> dict[str, bool]:
    return {
        key: any(status.get(key, False) for status in statuses)
        for key in REQUIRED_CHANNEL_RUNTIME_ENV_KEYS
    }


def _all_env_keys_ready(status: dict[str, bool], keys: tuple[str, ...]) -> bool:
    return all(status.get(key, False) for key in keys)


def _run_env_readiness_snapshot(cwd: Path) -> str:
    current_shell_status = _build_env_status(_read_current_shell_env_values())
    windows_env_status = _build_env_status(_read_windows_env_values())
    env_file_status = _build_env_status(_read_env_file_values(cwd))
    merged_status = _merge_env_statuses(current_shell_status, windows_env_status, env_file_status)
    if (
        _all_env_keys_ready(merged_status, LOCAL_RUNTIME_ENV_KEYS)
        and _all_env_keys_ready(merged_status, IMPORT_REFRESH_ENV_KEYS)
        and _all_env_keys_ready(merged_status, FOUR_CHANNEL_SMOKE_ENV_KEYS)
    ):
        return "four-channel cleanup smoke env ready"
    if _all_env_keys_ready(merged_status, LOCAL_RUNTIME_ENV_KEYS) and _all_env_keys_ready(
        merged_status, IMPORT_REFRESH_ENV_KEYS
    ):
        return "local runtime/import env ready; four-channel cleanup smoke env incomplete"
    if _all_env_keys_ready(merged_status, LOCAL_RUNTIME_ENV_KEYS):
        return "local runtime env ready; import/refresh env incomplete"
    return "missing local runtime env"


def _resolve_env_value(*, key: str, cwd: Path) -> str:
    current_shell_value = _read_current_shell_env_values().get(key, "").strip()
    if current_shell_value:
        return current_shell_value
    env_file_value = _read_env_file_values(cwd).get(key, "").strip()
    if env_file_value:
        return env_file_value
    return _read_windows_env_values().get(key, "").strip()


def _run_telegram_bot_api_snapshot(cwd: Path) -> str:
    token = _resolve_env_value(key="TELEGRAM_BOT_TOKEN", cwd=cwd)
    if not token:
        return "telegram bot token missing"
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=5) as response:
            payload = json.load(response)
    except (TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return "telegram bot api unreachable"
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return "telegram bot api rejected token"
    return "telegram bot api ready"


def _load_window_start_date(cwd: Path) -> str:
    window_text = (cwd / "docs/CLEANUP_VERIFICATION_WINDOW.md").read_text(encoding="utf-8")
    match = re.search(r"- 开始日期：(\d{4}-\d{2}-\d{2})", window_text)
    if match is None:
        raise CleanupVerificationDocsSyncError(
            "无法从 cleanup 验证窗口文档提取开始日期。",
            fix_hint="检查 docs/CLEANUP_VERIFICATION_WINDOW.md 是否仍保留 `- 开始日期：YYYY-MM-DD` 这一行。",
        )
    return match.group(1)


def _load_window_end_date(cwd: Path) -> str:
    window_text = (cwd / "docs/CLEANUP_VERIFICATION_WINDOW.md").read_text(encoding="utf-8")
    match = re.search(r"- 最早可结束日期：(\d{4}-\d{2}-\d{2})", window_text)
    if match is None:
        raise CleanupVerificationDocsSyncError(
            "无法从 cleanup 验证窗口文档提取结束日期。",
            fix_hint="检查 docs/CLEANUP_VERIFICATION_WINDOW.md 是否仍保留 `- 最早可结束日期：YYYY-MM-DD` 这一行。",
        )
    return match.group(1)


def _iter_cleanup_smoke_log_dates(cwd: Path) -> tuple[str, ...]:
    logs_dir = cwd / "logs"
    if not logs_dir.exists():
        return ()
    dates: list[str] = []
    for log_file in sorted(logs_dir.rglob("*")):
        if not log_file.is_file():
            continue
        with log_file.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                entry = parse_cleanup_private_chat_smoke_log_line(line)
                if entry is None:
                    continue
                dates.append(f"{entry.date_text}:{entry.channel}")
    return tuple(dates)


def _run_local_smoke_evidence_snapshot(cwd: Path) -> str:
    window_start_date = _load_window_start_date(cwd)
    window_end_date = _load_window_end_date(cwd)
    channels = tuple(channel for channel in EXPECTED_CLEANUP_SMOKE_CHANNELS if channel in {entry.partition(":")[2] for entry in _iter_cleanup_smoke_log_dates(cwd) if window_start_date <= entry.partition(":")[0] <= window_end_date})
    missing_channels = tuple(channel for channel in EXPECTED_CLEANUP_SMOKE_CHANNELS if channel not in channels)
    if channels:
        return "found in-window cleanup smoke evidence in repo: " + ",".join(channels) + (f"; missing channels: {','.join(missing_channels)}" if missing_channels else "; all channels covered")
    return "no in-window cleanup smoke evidence in repo; missing channels: " + ",".join(EXPECTED_CLEANUP_SMOKE_CHANNELS)


def _has_running_luminarr_process(proc_root: Path) -> bool:
    if not proc_root.exists():
        raise CleanupVerificationDocsSyncError(
            "无法访问进程信息目录。",
            fix_hint="检查当前环境是否提供 `/proc`，并确认同步脚本运行账户有读取 `cmdline` 的权限。",
        )
    for pid_dir in proc_root.iterdir():
        if not pid_dir.is_dir() or not pid_dir.name.isdigit():
            continue
        cmdline_path = pid_dir / "cmdline"
        if not cmdline_path.exists():
            continue
        try:
            raw_cmdline = cmdline_path.read_bytes()
        except OSError:
            continue
        tokens = [token.decode("utf-8", errors="ignore") for token in raw_cmdline.split(b"\0") if token]
        if not tokens:
            continue
        if "python" not in Path(tokens[0]).name:
            continue
        for index in range(len(tokens) - 1):
            if tokens[index] == "-m" and tokens[index + 1] == "app.main":
                return True
    return False


def _run_runtime_process_snapshot(_: Path) -> str:
    if _has_running_luminarr_process(Path("/proc")):
        return "luminarr process running"
    return "no luminarr process running"


SNAPSHOT_SPECS: dict[str, SnapshotSpec] = {
    "full_suite": SnapshotSpec(
        key="full_suite",
        command=(".venv/bin/python", "-m", "pytest", "-q"),
        command_display=".venv/bin/python -m pytest -q",
        result_kind="pytest",
        status_label="tests",
        status_style="date_first",
    ),
    "cleanup_service": SnapshotSpec(
        key="cleanup_service",
        command=(".venv/bin/python", "-m", "pytest", "-q", "tests/test_cleanup_downloaded_source.py"),
        command_display=".venv/bin/python -m pytest -q tests/test_cleanup_downloaded_source.py",
        result_kind="pytest",
        status_label="cleanup service tests",
        status_style="date_first",
    ),
    "smoke_gate": SnapshotSpec(
        key="smoke_gate",
        command=(".venv/bin/python", "-m", "pytest", "-q", "tests/test_cleanup_cross_channel_smoke.py"),
        command_display=".venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py",
        result_kind="pytest",
        status_label="four-channel cleanup smoke tests",
        status_style="result_first",
        window_label="最近一次聚合 smoke gate",
    ),
    "focused_cleanup": SnapshotSpec(
        key="focused_cleanup",
        command=(
            ".venv/bin/python",
            "-m",
            "pytest",
            "-q",
            "tests/test_cleanup_cross_channel_smoke.py",
            "tests/test_cleanup_downloaded_source.py",
            "tests/test_private_chat_runtime.py",
            "tests/test_personal_wechat_text.py",
            "tests/test_feishu_adapter.py",
            "tests/test_wecom_adapter.py",
            "tests/test_telegram_bot.py",
            "-k",
            "cleanup",
        ),
        command_display=(
            ".venv/bin/python -m pytest -q tests/test_cleanup_cross_channel_smoke.py "
            "tests/test_cleanup_downloaded_source.py tests/test_private_chat_runtime.py "
            "tests/test_personal_wechat_text.py tests/test_feishu_adapter.py "
            "tests/test_wecom_adapter.py tests/test_telegram_bot.py -k cleanup"
        ),
        result_kind="pytest",
        status_label="focused cleanup tests",
        status_style="result_first",
        window_label="最近一次 cleanup 协议回归验证",
    ),
    "docs_gate": SnapshotSpec(
        key="docs_gate",
        command=(
            ".venv/bin/python",
            "-m",
            "pytest",
            "-q",
            "tests/test_cleanup_docs_consistency.py",
            "tests/test_cleanup_verification_window_doc.py",
            "tests/test_cleanup_cross_channel_smoke.py",
        ),
        command_display=(
            ".venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py "
            "tests/test_cleanup_verification_window_doc.py tests/test_cleanup_cross_channel_smoke.py"
        ),
        result_kind="pytest",
        status_label="cleanup verification docs gate",
        status_style="result_first",
        window_label="最近一次 verification docs gate",
    ),
    "focused_config": SnapshotSpec(
        key="focused_config",
        command=(
            ".venv/bin/python",
            "-m",
            "pytest",
            "-q",
            "tests/test_config.py",
            "-k",
            "requires_token or requires_transmission_base_url or defaults_role_binding_to_first_instance or reads_tmdb_settings",
        ),
        command_display=(
            '.venv/bin/python -m pytest -q tests/test_config.py -k '
            '"requires_token or requires_transmission_base_url or '
            'defaults_role_binding_to_first_instance or reads_tmdb_settings"'
        ),
        result_kind="pytest",
        status_label="focused config truth tests",
        status_style="result_first",
    ),
    "makefile_env_guard": SnapshotSpec(
        key="makefile_env_guard",
        command=(".venv/bin/python", "-m", "pytest", "-q", "tests/test_makefile.py"),
        command_display=".venv/bin/python -m pytest -q tests/test_makefile.py",
        result_kind="pytest",
        status_label="make run env-file guard tests",
        status_style="result_first",
    ),
    "compile_check": SnapshotSpec(
        key="compile_check",
        command=("python3", "-m", "compileall", "app", "tests"),
        command_display="python3 -m compileall app tests",
        result_kind="compile",
        status_label="compile check",
        status_style="date_first",
    ),
    "docs_consistency": SnapshotSpec(
        key="docs_consistency",
        command=(".venv/bin/python", "-m", "pytest", "-q", "tests/test_cleanup_docs_consistency.py"),
        command_display=".venv/bin/python -m pytest -q tests/test_cleanup_docs_consistency.py",
        result_kind="pass_fail",
        status_label="docs consistency check",
        status_style="date_first",
    ),
    "env_readiness": SnapshotSpec(
        key="env_readiness",
        result_kind="custom",
        runner=_run_env_readiness_snapshot,
        command_display=ENV_READINESS_COMMAND_DISPLAY,
        status_label="env readiness snapshot",
        status_style="result_first",
        status_aliases=("current shell env readiness check",),
        window_label="当前环境就绪快照",
    ),
    "telegram_bot_api": SnapshotSpec(
        key="telegram_bot_api",
        result_kind="custom",
        runner=_run_telegram_bot_api_snapshot,
        command_display=TELEGRAM_BOT_API_COMMAND_DISPLAY,
        status_label="telegram bot api snapshot",
        status_style="result_first",
        window_label="当前 Telegram Bot API 就绪快照",
    ),
    "local_smoke_evidence": SnapshotSpec(
        key="local_smoke_evidence",
        result_kind="custom",
        runner=_run_local_smoke_evidence_snapshot,
        command_display=LOCAL_SMOKE_EVIDENCE_COMMAND_DISPLAY,
        status_label="local smoke evidence snapshot",
        status_style="result_first",
        window_label="当前仓库证据快照",
    ),
    "runtime_process": SnapshotSpec(
        key="runtime_process",
        result_kind="custom",
        runner=_run_runtime_process_snapshot,
        command_display=RUNTIME_PROCESS_COMMAND_DISPLAY,
        status_label="runtime process snapshot",
        status_style="result_first",
        window_label="当前运行进程快照",
    ),
}


def parse_pytest_result(stdout: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise CleanupVerificationDocsSyncError(
            "pytest 没有输出可解析的 summary。",
            fix_hint="检查命令是否真的执行到了 pytest，并确认没有被提前中断。",
        )
    summary = lines[-1]
    summary = re.sub(r" in \d+(?:\.\d+)?s(?: \(\d+:\d{2}:\d{2}\))?$", "", summary)
    if " passed" not in f" {summary}" and " failed" not in f" {summary}" and " skipped" not in f" {summary}":
        raise CleanupVerificationDocsSyncError(
            f"无法从 pytest 输出提取 summary：{summary}",
            fix_hint="检查 pytest 输出格式是否变化；必要时更新 cleanup_verification_docs.py 的解析规则。",
        )
    return summary


def run_snapshot(spec: SnapshotSpec, *, cwd: Path) -> SnapshotRun:
    if spec.runner is not None:
        result_text = spec.runner(cwd)
    else:
        completed = subprocess.run(
            spec.command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            command_output = "\n".join(
                part
                for part in (completed.stdout.strip(), completed.stderr.strip())
                if part
            ).strip()
            raise CleanupVerificationDocsSyncError(
                f"{spec.key} 执行失败：{spec.command_display}\n{command_output}",
                fix_hint="先修复对应测试或命令失败，再重新执行同步脚本；不要把失败结果写回 docs。",
            )
        if spec.result_kind == "pytest":
            result_text = parse_pytest_result(completed.stdout)
        elif spec.result_kind == "pass_fail":
            result_text = "passed"
        elif spec.result_kind == "compile":
            result_text = "passed"
        else:
            raise CleanupVerificationDocsSyncError(
                f"未知结果类型：{spec.result_kind}",
                fix_hint="检查 SNAPSHOT_SPECS 配置。",
            )
    return SnapshotRun(
        spec=spec,
        date_text=datetime.now(tz=SHANGHAI_TZ).date().isoformat(),
        result_text=result_text,
    )


def update_status_text(text: str, runs: list[SnapshotRun]) -> str:
    updated = text
    for run in runs:
        if not run.spec.status_label or not run.spec.status_style:
            continue
        updated = _replace_status_entry(updated, run)
    return updated


def update_window_text(text: str, runs: list[SnapshotRun]) -> str:
    updated = text
    for run in runs:
        if not run.spec.window_label:
            continue
        updated = _replace_window_entry(updated, run)
    return updated


def _replace_status_entry(text: str, run: SnapshotRun) -> str:
    labels = tuple(run.spec.status_aliases) + (run.spec.status_label or "",)
    label_pattern = "|".join(re.escape(label) for label in labels if label)
    command = run.spec.command_display
    if run.spec.status_style == "date_first":
        pattern = rf"^- (?:{label_pattern})：\d{{4}}-\d{{2}}-\d{{2}}，`[^`]+`（`[^`]+`）$"
        replacement = f"- {run.spec.status_label}：{run.date_text}，`{run.result_text}`（`{command}`）"
    elif run.spec.status_style == "result_first":
        pattern = rf"^- (?:{label_pattern})：`[^`]+`（\d{{4}}-\d{{2}}-\d{{2}}，`[^`]+`）$"
        replacement = f"- {run.spec.status_label}：`{run.result_text}`（{run.date_text}，`{command}`）"
    else:
        raise CleanupVerificationDocsSyncError(
            f"未知 status_style：{run.spec.status_style}",
            fix_hint="检查 SNAPSHOT_SPECS 配置。",
        )
    return _replace_single_line(
        text,
        pattern=pattern,
        replacement=replacement,
        missing_message=f"docs/STATUS.md 里缺少条目：{run.spec.status_label}",
    )


def _replace_window_entry(text: str, run: SnapshotRun) -> str:
    label = re.escape(run.spec.window_label or "")
    pattern = rf"^- {label}：\d{{4}}-\d{{2}}-\d{{2}}，`[^`]+`（`[^`]+`）$"
    replacement = f"- {run.spec.window_label}：{run.date_text}，`{run.result_text}`（`{run.spec.command_display}`）"
    return _replace_single_line(
        text,
        pattern=pattern,
        replacement=replacement,
        missing_message=f"docs/CLEANUP_VERIFICATION_WINDOW.md 里缺少条目：{run.spec.window_label}",
    )


def _replace_single_line(text: str, *, pattern: str, replacement: str, missing_message: str) -> str:
    updated, replaced_count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.MULTILINE)
    if replaced_count != 1:
        raise CleanupVerificationDocsSyncError(
            missing_message,
            fix_hint="检查对应 Markdown 行是否被改名或改格式；必要时同步更新同步脚本里的正则。",
        )
    return updated


def sync_documents(
    *,
    status_file: Path,
    window_file: Path,
    snapshot_keys: list[str],
    cwd: Path,
) -> list[SnapshotRun]:
    runs = [run_snapshot(SNAPSHOT_SPECS[key], cwd=cwd) for key in snapshot_keys]
    status_text = status_file.read_text(encoding="utf-8")
    window_text = window_file.read_text(encoding="utf-8")
    status_file.write_text(update_status_text(status_text, runs), encoding="utf-8")
    window_file.write_text(update_window_text(window_text, runs), encoding="utf-8")
    return runs


def build_argument_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="运行 cleanup 验证命令，并把固定快照同步回 docs/STATUS.md 与 docs/CLEANUP_VERIFICATION_WINDOW.md。",
    )
    parser.add_argument(
        "snapshots",
        nargs="+",
        choices=sorted(SNAPSHOT_SPECS),
        help="要执行并回填的快照键。",
    )
    parser.add_argument(
        "--status-file",
        default="docs/STATUS.md",
        help="要更新的 STATUS 文档路径。",
    )
    parser.add_argument(
        "--window-file",
        default="docs/CLEANUP_VERIFICATION_WINDOW.md",
        help="要更新的 cleanup 验证窗口文档路径。",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()
    cwd = Path.cwd()
    status_file = (cwd / args.status_file).resolve()
    window_file = (cwd / args.window_file).resolve()

    try:
        runs = sync_documents(
            status_file=status_file,
            window_file=window_file,
            snapshot_keys=args.snapshots,
            cwd=cwd,
        )
    except CleanupVerificationDocsSyncError as error:
        print(f"\033[31m[cleanup 文档快照同步失败]\033[0m {error}", flush=True)
        print(f"\033[33m[处理建议]\033[0m {error.fix_hint}", flush=True)
        return 1

    for run in runs:
        print(
            f"\033[32m[cleanup 文档快照已同步]\033[0m key={run.spec.key} "
            f"date={run.date_text} result={run.result_text}",
            flush=True,
        )
    print(
        f"\033[32m[cleanup 文档同步完成]\033[0m status={status_file} window={window_file}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
