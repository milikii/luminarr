from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from zoneinfo import ZoneInfo

from app.services.cleanup_downloaded_source import parse_cleanup_inspect_query, parse_cleanup_query


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
CLEANUP_PRIVATE_CHAT_SMOKE_LOG_LABEL = "[cleanup 私聊 smoke]"


@dataclass(frozen=True, slots=True)
class CleanupPrivateChatSmokeLogEntry:
    date_text: str
    channel: str
    action: str
    chat_id: int
    user_id: int
    query: str
    reply_head: str


def resolve_cleanup_private_chat_action(query: str) -> str | None:
    if parse_cleanup_inspect_query(query) is not None:
        return "cleanup_inspect"
    if parse_cleanup_query(query) is not None:
        return "cleanup"
    return None


def build_cleanup_private_chat_smoke_log_line(
    *,
    channel: str,
    query: str,
    reply_text: str,
    chat_id: int | None,
    user_id: int | None,
    date_text: str | None = None,
) -> str | None:
    action = resolve_cleanup_private_chat_action(query)
    if action is None:
        return None
    resolved_date = date_text or datetime.now(tz=SHANGHAI_TZ).date().isoformat()
    cleaned_channel = channel.strip().lower() or "unknown"
    cleaned_query = query.strip() or "-"
    reply_head = _summarize_reply_head(reply_text)
    return (
        f"\033[32m{CLEANUP_PRIVATE_CHAT_SMOKE_LOG_LABEL}\033[0m "
        f"date={resolved_date} channel={cleaned_channel} action={action} "
        f"chat_id={int(chat_id or 0)} user_id={int(user_id or 0)} "
        f"query={json.dumps(cleaned_query, ensure_ascii=False)} "
        f"reply_head={json.dumps(reply_head, ensure_ascii=False)}"
    )


def log_cleanup_private_chat_smoke(
    *,
    channel: str,
    query: str,
    reply_text: str,
    chat_id: int | None,
    user_id: int | None,
) -> None:
    log_line = build_cleanup_private_chat_smoke_log_line(
        channel=channel,
        query=query,
        reply_text=reply_text,
        chat_id=chat_id,
        user_id=user_id,
    )
    if log_line is None:
        return
    print(log_line, flush=True)


def parse_cleanup_private_chat_smoke_log_line(line: str) -> CleanupPrivateChatSmokeLogEntry | None:
    cleaned_line = ANSI_ESCAPE_RE.sub("", line).strip()
    prefix = f"{CLEANUP_PRIVATE_CHAT_SMOKE_LOG_LABEL} "
    if not cleaned_line.startswith(prefix):
        return None
    payload = cleaned_line[len(prefix):]
    match = re.fullmatch(
        r"date=(\d{4}-\d{2}-\d{2}) channel=([a-z_]+) action=(cleanup(?:_inspect)?) "
        r"chat_id=(-?\d+) user_id=(-?\d+) query=(\".*\") reply_head=(\".*\")",
        payload,
    )
    if match is None:
        return None
    try:
        query = json.loads(match.group(6))
        reply_head = json.loads(match.group(7))
    except json.JSONDecodeError:
        return None
    if not isinstance(query, str) or not isinstance(reply_head, str):
        return None
    return CleanupPrivateChatSmokeLogEntry(
        date_text=match.group(1),
        channel=match.group(2),
        action=match.group(3),
        chat_id=int(match.group(4)),
        user_id=int(match.group(5)),
        query=query,
        reply_head=reply_head,
    )


def _summarize_reply_head(reply_text: str) -> str:
    for line in reply_text.splitlines():
        cleaned_line = re.sub(r"\s+", " ", line.strip())
        if cleaned_line:
            return cleaned_line
    return "-"

