from __future__ import annotations

import hashlib
import re
import secrets
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from html import escape as escape_html
from typing import Any

from app.db.approval_repo import DEFAULT_PENDING_TIMEOUT_SECONDS
from app.services.search_reply_formatter import format_seeder_count, format_size, truncate_text

TELEGRAM_PT_RESOURCE_CARD_REPLY_PREFIX = "【PT资源卡】"
TELEGRAM_PT_RESOURCE_CALLBACK_PREFIX = "ptr"
TELEGRAM_PT_RESOURCE_CARD_STALE_TEXT = "这张 PT 资源卡已失效，请重新锁定作品后再搜索资源。"
TELEGRAM_PT_RESOURCE_CARD_CONSUMED_TEXT = "这张 PT 资源卡已经处理过了，请查看最近的下载待确认消息。"
TELEGRAM_PT_RESOURCE_CARD_STATE_UNAVAILABLE_TEXT = "PT 资源卡状态不可用，请重新锁定作品后再试。"
TELEGRAM_PT_RESOURCE_DETAIL_CHAR_LIMIT = 4096
TELEGRAM_PT_RESOURCE_PER_SITE_TARGET = 6

_PT_RESOURCE_CARD_REPLY_RE = re.compile(r"^【PT资源卡】\s+(?P<session>[a-f0-9]{8})$")
_PT_RESOURCE_CALLBACK_RE = re.compile(r"^ptr:(?P<session>[a-f0-9]{8}):s:(?P<slot>[1-9]\d{0,2})$")


@dataclass(slots=True)
class TelegramPtResourceCardSession:
    session_token: str
    chat_id: int
    title: str
    original_title: str
    year: str
    media_type: str
    poster_url: str
    overview: str
    resource_snapshot_id: str
    resource_items: tuple[dict[str, Any], ...]
    partial_failure_hint: str = ""
    message_id: int | None = None
    selected_index: int | None = None
    consumed_at: float | None = None
    expires_at: float = 0.0
    status: str = "active"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class TelegramPtResourceCardSelectionResult:
    status: str
    rejection_text: str = ""
    session: TelegramPtResourceCardSession | None = None
    candidate: Mapping[str, Any] | None = None
    selection_index: int | None = None


class TelegramPtResourceCardState:
    def __init__(self, *, ttl_seconds: int = DEFAULT_PENDING_TIMEOUT_SECONDS) -> None:
        self._ttl_seconds = max(60, int(ttl_seconds))
        self._sessions_by_token: dict[str, TelegramPtResourceCardSession] = {}
        self._session_tokens_by_chat: dict[int, set[str]] = {}

    def create_session(
        self,
        *,
        chat_id: int,
        title: str,
        original_title: str,
        year: str,
        media_type: str,
        poster_url: str,
        overview: str,
        resource_items: Sequence[Mapping[str, Any]],
        partial_failure_hint: str = "",
    ) -> TelegramPtResourceCardSession:
        cleaned_chat_id = int(chat_id)
        self.invalidate_chat_sessions(chat_id=cleaned_chat_id)
        cleaned_items = tuple(_normalize_resource_item(item) for item in resource_items)
        now = time.time()
        session = TelegramPtResourceCardSession(
            session_token=_build_session_token(),
            chat_id=cleaned_chat_id,
            title=title.strip() or "-",
            original_title=original_title.strip(),
            year=year.strip() or "-",
            media_type=media_type.strip() or "-",
            poster_url=poster_url.strip(),
            overview=overview.strip(),
            resource_snapshot_id=_build_resource_snapshot_id(cleaned_items),
            resource_items=cleaned_items,
            partial_failure_hint=partial_failure_hint.strip(),
            expires_at=now + self._ttl_seconds,
            created_at=now,
        )
        self._sessions_by_token[session.session_token] = session
        self._session_tokens_by_chat.setdefault(cleaned_chat_id, set()).add(session.session_token)
        return session

    def get_session(self, session_token: str) -> TelegramPtResourceCardSession | None:
        cleaned_token = session_token.strip().lower()
        if not cleaned_token:
            return None
        session = self._sessions_by_token.get(cleaned_token)
        if session is None:
            return None
        self._mark_expired_if_needed(session)
        return session

    def register_message(self, session_token: str, message_id: int | None) -> bool:
        session = self.get_session(session_token)
        if session is None:
            return False
        if isinstance(message_id, int) and message_id > 0:
            session.message_id = message_id
        return True

    def invalidate_chat_sessions(self, *, chat_id: int, keep_session_token: str = "") -> None:
        cleaned_keep = keep_session_token.strip().lower()
        tokens = tuple(self._session_tokens_by_chat.get(int(chat_id), set()))
        for token in tokens:
            if cleaned_keep and token == cleaned_keep:
                continue
            session = self._sessions_by_token.get(token)
            if session is None:
                continue
            self._mark_expired_if_needed(session)
            if session.status == "active":
                session.status = "cancelled"

    def consume_selection(
        self,
        *,
        session_token: str,
        chat_id: int,
        selection_index: int,
    ) -> TelegramPtResourceCardSelectionResult:
        session = self.get_session(session_token)
        if session is None:
            return TelegramPtResourceCardSelectionResult(
                status="missing",
                rejection_text=TELEGRAM_PT_RESOURCE_CARD_STATE_UNAVAILABLE_TEXT,
            )
        if session.chat_id != int(chat_id):
            return TelegramPtResourceCardSelectionResult(
                status="stale",
                rejection_text=TELEGRAM_PT_RESOURCE_CARD_STALE_TEXT,
                session=session,
            )
        if session.status == "selected":
            return TelegramPtResourceCardSelectionResult(
                status="consumed",
                rejection_text=TELEGRAM_PT_RESOURCE_CARD_CONSUMED_TEXT,
                session=session,
            )
        if session.status in {"cancelled", "expired"}:
            return TelegramPtResourceCardSelectionResult(
                status=session.status,
                rejection_text=TELEGRAM_PT_RESOURCE_CARD_STALE_TEXT,
                session=session,
            )
        if selection_index < 1 or selection_index > len(session.resource_items):
            return TelegramPtResourceCardSelectionResult(
                status="stale",
                rejection_text=TELEGRAM_PT_RESOURCE_CARD_STALE_TEXT,
                session=session,
            )
        session.selected_index = selection_index
        session.consumed_at = time.time()
        session.status = "selected"
        return TelegramPtResourceCardSelectionResult(
            status="selected",
            session=session,
            candidate=session.resource_items[selection_index - 1],
            selection_index=selection_index,
        )

    def _mark_expired_if_needed(self, session: TelegramPtResourceCardSession) -> None:
        if session.status != "active":
            return
        if session.expires_at <= time.time():
            session.status = "expired"


def build_telegram_pt_resource_reply_marker(session_token: str) -> str:
    cleaned_token = session_token.strip().lower()
    return f"{TELEGRAM_PT_RESOURCE_CARD_REPLY_PREFIX} {cleaned_token}".strip()


def parse_telegram_pt_resource_reply_marker(text: str) -> str | None:
    matched = _PT_RESOURCE_CARD_REPLY_RE.match(text.strip())
    if matched is None:
        return None
    return str(matched.group("session") or "").strip().lower() or None


def build_telegram_pt_resource_callback_data(session_token: str, selection_index: int) -> str:
    cleaned_token = session_token.strip().lower()
    return f"{TELEGRAM_PT_RESOURCE_CALLBACK_PREFIX}:{cleaned_token}:s:{int(selection_index)}"


def parse_telegram_pt_resource_callback_data(data: str) -> tuple[str, int] | None:
    matched = _PT_RESOURCE_CALLBACK_RE.match(data.strip())
    if matched is None:
        return None
    session_token = str(matched.group("session") or "").strip().lower()
    selection_index = int(str(matched.group("slot") or "0"))
    if not session_token or selection_index <= 0:
        return None
    return session_token, selection_index


def build_telegram_pt_resource_task_ref(session_token: str, selection_index: int) -> str:
    return f"pt-{session_token.strip().lower()}-{int(selection_index)}"


def prepare_telegram_pt_resource_items(
    *,
    title: str,
    year: str,
    resource_items: Sequence[Mapping[str, Any]],
    detail_char_limit: int = TELEGRAM_PT_RESOURCE_DETAIL_CHAR_LIMIT,
    per_site_target: int = TELEGRAM_PT_RESOURCE_PER_SITE_TARGET,
) -> tuple[dict[str, Any], ...]:
    normalized_items = tuple(_normalize_resource_item(item) for item in resource_items)
    if not normalized_items:
        return ()
    grouped_items = _group_pt_resource_items_by_site(normalized_items)
    prioritized_items: list[dict[str, Any]] = []
    for _site_name, site_items in grouped_items:
        prioritized_items.extend(_select_site_resource_items(site_items, per_site_target=per_site_target))
    selected_items: list[dict[str, Any]] = []
    for item in prioritized_items:
        candidate_items = (*selected_items, item)
        detail_text = format_telegram_pt_resource_detail_text(
            title=title,
            year=year,
            resource_items=candidate_items,
        )
        if len(detail_text) > max(512, int(detail_char_limit)) and selected_items:
            break
        selected_items.append(item)
    return tuple(selected_items) if selected_items else normalized_items[:1]


def format_telegram_pt_resource_card_caption(*, session: TelegramPtResourceCardSession) -> str:
    lines = [f"🎬 <b>{escape_html(session.title)} ({escape_html(session.year)})</b>"]
    if session.original_title and session.original_title.casefold() != session.title.casefold():
        lines.append(f"<i>{escape_html(session.original_title)}</i>")
    lines.append(f"🎞 <b>类型：</b> {escape_html(session.media_type)}")
    if session.overview:
        lines.append(f"📝 <b>简介：</b> {escape_html(truncate_text(session.overview, limit=90))}")
    lines.append("👇 <b>点下方按钮选择资源，详见下一条消息。</b>")
    return "\n".join(lines).strip()


def format_telegram_pt_resource_detail_message(*, session: TelegramPtResourceCardSession) -> str:
    return format_telegram_pt_resource_detail_text(
        title=session.title,
        year=session.year,
        resource_items=session.resource_items,
        partial_failure_hint=session.partial_failure_hint,
    )


def _normalize_resource_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in item.items()}


def _build_session_token() -> str:
    return secrets.token_hex(4)


def _build_resource_snapshot_id(resource_items: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for item in resource_items:
        digest.update(str(item.get("title", "")).strip().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(item.get("downloadUrl", "") or item.get("source", "")).strip().encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:12]


def format_telegram_pt_resource_detail_text(
    *,
    title: str,
    year: str,
    resource_items: Sequence[Mapping[str, Any]],
    partial_failure_hint: str = "",
) -> str:
    normalized_items = tuple(_normalize_resource_item(item) for item in resource_items)
    lines = [
        "🧾 <b>PT 资源详情</b>",
        f"🎬 <b>{escape_html(title.strip() or '-')} ({escape_html(year.strip() or '-')})</b>",
        "以下编号与上方按钮一致，点击按钮即可创建下载待确认。",
    ]
    if partial_failure_hint.strip():
        lines.append(f"⚠️ {escape_html(partial_failure_hint.strip())}")
    for site_name, numbered_items in _group_numbered_pt_resource_items_by_site(normalized_items):
        lines.extend(("", f"<b>{escape_html(site_name)}</b>"))
        for index, item in numbered_items:
            quality = escape_html(_resolve_pt_quality_label(item))
            size = escape_html(format_size(item.get("size")))
            seeders = escape_html(format_seeder_count(item.get("seeders")))
            title_line = escape_html(truncate_text(str(item.get("title", "")).strip() or "(no title)", limit=88))
            lines.append(f"【{index}】<b>{quality}</b> ｜ 💾 {size} ｜ 🌱 {seeders}")
            lines.append(title_line)
    return "\n".join(lines).strip()


def _group_numbered_pt_resource_items_by_site(
    resource_items: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, tuple[tuple[int, dict[str, Any]], ...]], ...]:
    groups: list[tuple[str, list[tuple[int, dict[str, Any]]]]] = []
    positions_by_site: dict[str, int] = {}
    for index, raw_item in enumerate(resource_items, start=1):
        item = _normalize_resource_item(raw_item)
        site_name = _resolve_pt_site_name(item)
        site_position = positions_by_site.get(site_name)
        if site_position is None:
            groups.append((site_name, [(index, item)]))
            positions_by_site[site_name] = len(groups) - 1
            continue
        groups[site_position][1].append((index, item))
    return tuple((site_name, tuple(items)) for site_name, items in groups)


def _group_pt_resource_items_by_site(
    resource_items: Sequence[dict[str, Any]],
) -> tuple[tuple[str, tuple[dict[str, Any], ...]], ...]:
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    positions_by_site: dict[str, int] = {}
    for item in resource_items:
        site_name = _resolve_pt_site_name(item)
        site_position = positions_by_site.get(site_name)
        if site_position is None:
            groups.append((site_name, [item]))
            positions_by_site[site_name] = len(groups) - 1
            continue
        groups[site_position][1].append(item)
    return tuple((site_name, tuple(items)) for site_name, items in groups)


def _select_site_resource_items(
    site_items: Sequence[dict[str, Any]],
    *,
    per_site_target: int,
) -> tuple[dict[str, Any], ...]:
    limit = max(1, int(per_site_target))
    selected_indexes: list[int] = []
    for resolution in ("2160p", "1440p", "1080p"):
        for index, item in enumerate(site_items):
            if index in selected_indexes:
                continue
            if _resolve_pt_resolution_token(item) != resolution:
                continue
            selected_indexes.append(index)
            break
    for index, _item in enumerate(site_items):
        if index in selected_indexes:
            continue
        selected_indexes.append(index)
        if len(selected_indexes) >= limit:
            break
    selected_indexes = selected_indexes[:limit]
    return tuple(site_items[index] for index in selected_indexes)


def _resolve_pt_site_name(item: Mapping[str, Any]) -> str:
    return str(item.get("indexerName", "") or item.get("indexer", "")).strip() or "-"


def _resolve_pt_quality_label(item: Mapping[str, Any]) -> str:
    quality = str(item.get("quality", "")).strip()
    if quality:
        return quality
    resolution = _resolve_pt_resolution_token(item)
    if resolution:
        return resolution
    return "-"


def _resolve_pt_resolution_token(item: Mapping[str, Any]) -> str:
    text = " ".join(
        part
        for part in (
            str(item.get("quality", "")).strip(),
            str(item.get("resolution", "")).strip(),
            str(item.get("title", "")).strip(),
        )
        if part
    ).lower()
    if not text:
        return ""
    if "2160p" in text or re.search(r"\b4k\b", text) is not None:
        return "2160p"
    if "1440p" in text or re.search(r"\b2k\b", text) is not None:
        return "1440p"
    if "1080p" in text:
        return "1080p"
    if "720p" in text:
        return "720p"
    return ""
