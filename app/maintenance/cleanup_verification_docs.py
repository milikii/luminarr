from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class CleanupVerificationDocsSyncError(RuntimeError):
    def __init__(self, message: str, *, fix_hint: str) -> None:
        super().__init__(message)
        self.fix_hint = fix_hint


@dataclass(frozen=True, slots=True)
class SnapshotSpec:
    key: str
    command: tuple[str, ...]
    command_display: str
    result_kind: str
    status_label: str | None = None
    status_style: str | None = None
    window_label: str | None = None


@dataclass(frozen=True, slots=True)
class SnapshotRun:
    spec: SnapshotSpec
    date_text: str
    result_text: str


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
    label = re.escape(run.spec.status_label or "")
    command = run.spec.command_display
    if run.spec.status_style == "date_first":
        pattern = rf"^- {label}：\d{{4}}-\d{{2}}-\d{{2}}，`[^`]+`（`[^`]+`）$"
        replacement = f"- {run.spec.status_label}：{run.date_text}，`{run.result_text}`（`{command}`）"
    elif run.spec.status_style == "result_first":
        pattern = rf"^- {label}：`[^`]+`（\d{{4}}-\d{{2}}-\d{{2}}，`[^`]+`）$"
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
    updated, replaced_count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
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
