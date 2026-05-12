from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.operational_logging import emit_operational_log, strip_ansi_escape, summarize_first_non_empty_line

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
TRACE_LOG_LABEL = "[trace]"
DEFAULT_TRACE_LOG_FILE = "trace.log"
TRACE_LOG_PATH_BOT_DATA_KEY = "trace_log_path"


@dataclass(frozen=True, slots=True)
class TraceLogEntry:
    timestamp_text: str
    scope: str
    event: str
    result: str
    channel: str
    workflow: str
    action: str
    stage: str
    chat_id: int
    user_id: int
    task_ref: str
    task_id: str
    task_hash: str
    query: str
    reply_head: str
    detail: str


def configure_trace_log_file(
    *,
    log_dir: Path,
    file_name: str = DEFAULT_TRACE_LOG_FILE,
) -> Path | None:
    log_path = log_dir / file_name
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        emit_operational_log(
            title="trace 日志目录不可写",
            detail=f"路径={log_path.parent} 错误={error}",
            fix_hint=(
                "检查 `LUMINARR_LOG_DIR`、当前工作目录和 logs 目录权限；"
                "确认 `make run` / `.venv/bin/python -m app.main` 使用的是可写目录。"
            ),
        )
        return None
    return log_path


def build_trace_log_line(
    *,
    scope: str,
    event: str,
    result: str,
    channel: str = "",
    workflow: str = "",
    action: str = "",
    stage: str = "",
    chat_id: int | None = None,
    user_id: int | None = None,
    task_ref: str = "",
    task_id: str = "",
    task_hash: str = "",
    query: str = "",
    reply_text: str = "",
    detail: str = "",
    timestamp_text: str | None = None,
) -> str:
    payload = {
        "timestamp_text": timestamp_text or datetime.now(tz=SHANGHAI_TZ).isoformat(timespec="seconds"),
        "scope": scope.strip() or "unknown",
        "event": event.strip() or "unknown",
        "result": result.strip() or "unknown",
        "channel": channel.strip().lower() or "unknown",
        "workflow": workflow.strip() or "-",
        "action": action.strip() or "-",
        "stage": stage.strip() or "-",
        "chat_id": int(chat_id or 0),
        "user_id": int(user_id or 0),
        "task_ref": task_ref.strip() or "-",
        "task_id": task_id.strip() or "-",
        "task_hash": task_hash.strip() or "-",
        "query": query.strip() or "-",
        "reply_head": _summarize_reply_head(reply_text),
        "detail": detail.strip() or "-",
    }
    return f"\033[36m{TRACE_LOG_LABEL}\033[0m {json.dumps(payload, ensure_ascii=False)}"


def log_trace_event(
    *,
    scope: str,
    event: str,
    result: str,
    log_path: Path | None,
    channel: str = "",
    workflow: str = "",
    action: str = "",
    stage: str = "",
    chat_id: int | None = None,
    user_id: int | None = None,
    task_ref: str = "",
    task_id: str = "",
    task_hash: str = "",
    query: str = "",
    reply_text: str = "",
    detail: str = "",
) -> None:
    if log_path is None:
        return
    log_line = build_trace_log_line(
        scope=scope,
        event=event,
        result=result,
        channel=channel,
        workflow=workflow,
        action=action,
        stage=stage,
        chat_id=chat_id,
        user_id=user_id,
        task_ref=task_ref,
        task_id=task_id,
        task_hash=task_hash,
        query=query,
        reply_text=reply_text,
        detail=detail,
    )
    print(log_line, flush=True)
    _append_trace_log_line(log_line, log_path=log_path)


def parse_trace_log_line(line: str) -> TraceLogEntry | None:
    cleaned_line = strip_ansi_escape(line).strip()
    prefix = f"{TRACE_LOG_LABEL} "
    if not cleaned_line.startswith(prefix):
        return None
    payload_text = cleaned_line[len(prefix):]
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return TraceLogEntry(
            timestamp_text=str(payload["timestamp_text"]),
            scope=str(payload["scope"]),
            event=str(payload["event"]),
            result=str(payload["result"]),
            channel=str(payload["channel"]),
            workflow=str(payload["workflow"]),
            action=str(payload["action"]),
            stage=str(payload["stage"]),
            chat_id=int(payload["chat_id"]),
            user_id=int(payload["user_id"]),
            task_ref=str(payload["task_ref"]),
            task_id=str(payload["task_id"]),
            task_hash=str(payload["task_hash"]),
            query=str(payload["query"]),
            reply_head=str(payload["reply_head"]),
            detail=str(payload["detail"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _summarize_reply_head(reply_text: str) -> str:
    return summarize_first_non_empty_line(reply_text)


def _append_trace_log_line(log_line: str, *, log_path: Path) -> None:
    cleaned_line = strip_ansi_escape(log_line)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{cleaned_line}\n")
    except OSError as error:
        emit_operational_log(
            title="trace 日志落盘失败",
            detail=f"路径={log_path} 错误={error}",
            fix_hint=(
                "检查 `LUMINARR_LOG_DIR` 是否可写，确认没有把同名路径占成文件或只读挂载；"
                "修复后重新运行应用。"
            ),
        )
