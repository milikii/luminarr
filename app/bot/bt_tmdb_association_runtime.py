from __future__ import annotations

import json
import sqlite3
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from typing import Literal, Protocol

from app.bot.bt_classification_runtime import BT_CLASSIFICATION_PROMPT_TEXT, set_bt_classification_pending
from app.bot.raw_bt_destination_runtime import can_dispatch_bt_source
from app.clients.tmdb import TmdbMovie
from app.db.bt_pending_repo import (
    BT_PENDING_STAGE_TMDB_ASSOCIATION,
    BtPendingPersistenceError,
    BtPendingRepo,
)
from app.services.add_to_downloader import BT_SOURCE_UNSUPPORTED_TEXT, AddToDownloaderService
from app.services.search_request_context import parse_movie_query

BT_TMDB_ASSOCIATION_PROMPT_TEXT_TEMPLATE = (
    "已记录本次 BT 分类：{label}（{kind}）。\n"
    "请继续发送片名，可带年份，例如：{example}\n"
    "当前这一步只做 TMDB 关联，不会执行下载投递。"
)
BT_TMDB_ASSOCIATION_PENDING_REMINDER_TEMPLATE = (
    "当前正在等待 {label} 的 TMDB 关联标题。\n"
    "请发送：片名 或 片名 + 年份，例如：{example}"
)
BT_TMDB_ASSOCIATION_CANCELLED_TEXT = "已取消当前 BT TMDB 关联，请重新发送磁力或 BT 指令。"
BT_TMDB_ASSOCIATION_NOT_FOUND_TEMPLATE = (
    "未找到可用的 TMDB 关联：{query}\n"
    "请补充更准确的片名，可带年份，例如：{example}\n"
    "如果这不是影视资源，请改选 raw_bt。"
)
BT_TMDB_ASSOCIATION_AMBIGUOUS_TEMPLATE = (
    "TMDB 关联存在多个候选：{query}\n"
    "请补充年份或更完整片名后重试。\n"
    "参考候选：\n"
    "{options}"
)
BT_TMDB_ASSOCIATION_SUCCESS_TEMPLATE = (
    "BT {label} TMDB 关联成功。\n"
    "标题: {title}\n"
    "原始标题: {original_title}\n"
    "年份: {year}\n"
    "TMDB ID: {tmdb_id}"
)
BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT = "TMDB 关联服务未就绪，请稍后重试。"
BT_TMDB_ASSOCIATION_PENDING_BY_CHAT_KEY = "bt_tmdb_association_pending_by_chat"
BT_TMDB_ASSOCIATION_EXAMPLES = {
    "movie": "Dune 2021",
    "series": "三体 2023",
    "anime": "葬送的芙莉莲 2023",
}
BT_CLASSIFICATION_LABELS = {
    "movie": "电影",
    "series": "剧集",
    "anime": "动漫",
}


@dataclass(frozen=True, slots=True)
class BtTmdbAssociationPending:
    media_kind: str
    source: str


class ResolvedDownloaderExecutionLike(Protocol):
    name: str
    downloader_type: str
    download_dir: str


def resolve_bt_tmdb_candidates_lookup(
    *,
    bot_data: MutableMapping[str, object],
    media_kind: str,
    bt_tmdb_movie_candidates_lookup_key: str,
    bt_tmdb_tv_candidates_lookup_key: str,
) -> Callable[[str, str], Awaitable[list[TmdbMovie]]] | None:
    lookup_key = bt_tmdb_movie_candidates_lookup_key
    if media_kind in {"series", "anime"}:
        lookup_key = bt_tmdb_tv_candidates_lookup_key
    lookup_func = bot_data.get(lookup_key)
    if callable(lookup_func):
        return lookup_func
    return None


def log_bt_tmdb_association_error(*, media_kind: str, query: str, error: Exception) -> None:
    print(
        f"\033[31m[BT TMDB 关联失败]\033[0m 类型={media_kind} 查询={query} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 TMDB_API_KEY、TMDB_BASE_URL 和网络连通性后重试。"
    )


def _resolve_bt_tmdb_association_pending_by_chat(
    bot_data: MutableMapping[str, object],
) -> dict[int, BtTmdbAssociationPending]:
    pending_by_chat = bot_data.get(BT_TMDB_ASSOCIATION_PENDING_BY_CHAT_KEY)
    if isinstance(pending_by_chat, dict):
        return pending_by_chat
    resolved_pending_by_chat: dict[int, BtTmdbAssociationPending] = {}
    bot_data[BT_TMDB_ASSOCIATION_PENDING_BY_CHAT_KEY] = resolved_pending_by_chat
    return resolved_pending_by_chat


def _resolve_bt_pending_repo(
    bot_data: MutableMapping[str, object],
    bt_pending_repo_key: str,
) -> BtPendingRepo | None:
    pending_repo = bot_data.get(bt_pending_repo_key)
    if isinstance(pending_repo, BtPendingRepo):
        return pending_repo
    return None


def _serialize_bt_pending_payload(payload: dict[str, object]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return "{}"


def _deserialize_bt_pending_payload(payload_json: str) -> tuple[dict[str, object], str | None]:
    if not payload_json.strip():
        return {}, "payload_json empty"
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}, "payload_json invalid json"
    if not isinstance(payload, dict):
        return {}, "payload_json not object"
    return payload, None


def _log_bt_pending_payload_corruption(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理载荷损坏]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state.payload_json 是否仍是合法 JSON，且包含当前 stage 需要的字段。",
        flush=True,
    )


def _log_bt_pending_clear_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理清理失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表删除是否正常；当前进程内待处理状态已尽量清掉，但重启后旧状态可能仍残留。",
        flush=True,
    )


def _log_bt_pending_clear_result_missing(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理清理结果缺失]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 删除返回是否仍带有明确结果；当前进程内待处理状态已尽量回滚，避免把缺失真相误判成已清理成功。",
        flush=True,
    )


def _log_bt_pending_read_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理读取失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表读取是否正常；当前相关入口会按状态不可用处理，避免把 SQLite 读取异常误判成“没有待处理状态”。",
        flush=True,
    )


def _log_bt_pending_row_corrupted(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理记录损坏]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state.stage 是否仍是完整真相；当前相关入口会按状态不可用处理，避免把坏记录误判成“没有待处理状态”。",
        flush=True,
    )


def _log_bt_pending_persist_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理持久化失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表写入是否正常；当前进程内待处理状态仍保留，但重启后可能丢失这一步的上下文。",
        flush=True,
    )


def _log_bt_pending_missing_after_upsert(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理写入后记录缺失]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表是否被并发删除或触发器回滚；"
        "如需继续当前 BT follow-up，请先确认 SQLite 写入后能立即回读该记录。",
        flush=True,
    )


def set_bt_tmdb_association_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    media_kind: str,
    source: str,
    bt_pending_repo_key: str = "bt_pending_repo",
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_tmdb_association_pending_by_chat(bot_data)
    pending_by_chat[chat_id] = BtTmdbAssociationPending(media_kind=media_kind, source=source.strip())
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return True
    try:
        pending_repo.upsert_pending(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
            payload_json=_serialize_bt_pending_payload({"media_kind": media_kind, "source": source.strip()}),
        )
    except BtPendingPersistenceError as error:
        if str(error) == "bt_pending_state missing after upsert":
            _log_bt_pending_missing_after_upsert(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_persist_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
                reason=str(error),
            )
        pending_by_chat.pop(chat_id, None)
        return False
    except sqlite3.Error as error:
        _log_bt_pending_persist_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
            reason=str(error),
        )
        pending_by_chat.pop(chat_id, None)
        return False
    return True


def get_bt_tmdb_association_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    bt_pending_repo_key: str = "bt_pending_repo",
) -> BtTmdbAssociationPending | None | Literal[False]:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_bt_tmdb_association_pending_by_chat(bot_data)
    pending = pending_by_chat.get(chat_id)
    if isinstance(pending, BtTmdbAssociationPending):
        return pending
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return None
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except (BtPendingPersistenceError, sqlite3.Error) as error:
        if str(error) == "bt_pending_state stage empty after read":
            _log_bt_pending_row_corrupted(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_read_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
                reason=str(error),
            )
        return False
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_TMDB_ASSOCIATION:
        return None
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return False
    media_kind = str(payload.get("media_kind", "")).strip()
    source = str(payload.get("source", "")).strip()
    if not media_kind:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.media_kind missing",
        )
        return False
    if not source:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.source missing",
        )
        return False
    resolved_pending = BtTmdbAssociationPending(media_kind=media_kind, source=source)
    pending_by_chat[chat_id] = resolved_pending
    return resolved_pending


def clear_bt_tmdb_association_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    bt_pending_repo_key: str = "bt_pending_repo",
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_tmdb_association_pending_by_chat(bot_data)
    pending = pending_by_chat.pop(chat_id, None)
    cleared = pending is not None
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return cleared
    try:
        cleared_result = pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_TMDB_ASSOCIATION)
        if cleared_result is None:
            raise BtPendingPersistenceError("bt_pending_state clear result missing")
        return cleared_result or cleared
    except (BtPendingPersistenceError, sqlite3.Error) as error:
        if str(error) == "bt_pending_state clear result missing":
            _log_bt_pending_clear_result_missing(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_TMDB_ASSOCIATION, reason=str(error))
        if pending is not None:
            pending_by_chat[chat_id] = pending
        return None


def enter_media_import_bt_flow(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    source: str,
    media_kind: str | None = None,
    bt_pending_repo_key: str = "bt_pending_repo",
    service_not_ready_text: str,
    bt_classification_prompt_text: str = BT_CLASSIFICATION_PROMPT_TEXT,
) -> str:
    if media_kind is not None:
        if not set_bt_tmdb_association_pending(
            bot_data=bot_data,
            chat_id=chat_id,
            media_kind=media_kind,
            source=source,
            bt_pending_repo_key=bt_pending_repo_key,
        ):
            return service_not_ready_text
        return format_bt_tmdb_association_prompt(media_kind)
    if not set_bt_classification_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        query=source,
        bt_pending_repo_key=bt_pending_repo_key,
    ):
        return service_not_ready_text
    return bt_classification_prompt_text


def format_bt_tmdb_association_prompt(media_kind: str) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, media_kind)
    example = BT_TMDB_ASSOCIATION_EXAMPLES.get(media_kind, "Dune 2021")
    return BT_TMDB_ASSOCIATION_PROMPT_TEXT_TEMPLATE.format(label=label, kind=media_kind, example=example)


def format_bt_tmdb_association_pending_reminder(media_kind: str) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, media_kind)
    example = BT_TMDB_ASSOCIATION_EXAMPLES.get(media_kind, "Dune 2021")
    return BT_TMDB_ASSOCIATION_PENDING_REMINDER_TEMPLATE.format(label=label, example=example)


def format_bt_tmdb_association_options(options: list[TmdbMovie]) -> str:
    lines: list[str] = []
    for index, option in enumerate(options, start=1):
        title = option.title or option.original_title or "-"
        year = option.year or "-"
        lines.append(f"{index}. {title} ({year}) [TMDB ID: {option.tmdb_id or '-'}]")
    return "\n".join(lines) if lines else "- 暂无可区分候选，请直接补充年份。"


def format_bt_tmdb_association_success(media_kind: str, match: TmdbMovie) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, media_kind)
    title = match.title or match.original_title or "-"
    original_title = match.original_title or title
    year = match.year or "-"
    tmdb_id = match.tmdb_id or "-"
    return BT_TMDB_ASSOCIATION_SUCCESS_TEMPLATE.format(
        label=label,
        title=title,
        original_title=original_title,
        year=year,
        tmdb_id=tmdb_id,
    )


def format_bt_dispatch_title(match: TmdbMovie) -> str:
    title = match.title or match.original_title or "(no title)"
    year = match.year.strip()
    if not year:
        return title
    return f"{title} ({year})"


async def handle_bt_tmdb_association_query(
    *,
    query: str,
    pending: BtTmdbAssociationPending,
    chat_id: int | None,
    user_id: int | None,
    bot_data: MutableMapping[str, object],
    add_to_downloader_service_key: str,
    clear_pending: Callable[[], bool | None],
    resolve_candidates_lookup: Callable[[str], Callable[[str, str], Awaitable[list[TmdbMovie]]] | None],
    resolve_downloader_execution: Callable[[], tuple[ResolvedDownloaderExecutionLike | None, str | None]],
    log_bt_tmdb_association_error: Callable[[str, str, Exception], None],
    service_not_ready_text: str,
    bt_tmdb_association_service_not_ready_text: str,
    bt_source_required_text: str,
) -> str:
    if chat_id is None:
        return service_not_ready_text
    parsed_query = parse_movie_query(query)
    if not parsed_query.title:
        return format_bt_tmdb_association_pending_reminder(pending.media_kind)

    lookup_func = resolve_candidates_lookup(pending.media_kind)
    if lookup_func is None:
        return bt_tmdb_association_service_not_ready_text

    try:
        matches = await lookup_func(parsed_query.title, parsed_query.year)
    except Exception as error:
        log_bt_tmdb_association_error(pending.media_kind, query, error)
        return bt_tmdb_association_service_not_ready_text

    if not matches:
        example = BT_TMDB_ASSOCIATION_EXAMPLES.get(pending.media_kind, "Dune 2021")
        return BT_TMDB_ASSOCIATION_NOT_FOUND_TEMPLATE.format(query=query.strip(), example=example)

    if not parsed_query.year and len(matches) > 1:
        return BT_TMDB_ASSOCIATION_AMBIGUOUS_TEMPLATE.format(
            query=query.strip(),
            options=format_bt_tmdb_association_options(matches),
        )

    cleared_tmdb_association = clear_pending()
    if cleared_tmdb_association is None:
        return service_not_ready_text
    association_text = format_bt_tmdb_association_success(pending.media_kind, matches[0])
    if not can_dispatch_bt_source(pending.source):
        return f"{association_text}\n\n{bt_source_required_text}"
    add_service = bot_data.get(add_to_downloader_service_key)
    if not isinstance(add_service, AddToDownloaderService):
        return service_not_ready_text
    downloader_execution, resolution_error = resolve_downloader_execution()
    if resolution_error is not None:
        return resolution_error
    pending_text = await add_service.add_bt_source(
        chat_id=chat_id,
        user_id=user_id,
        source=pending.source,
        title=format_bt_dispatch_title(matches[0]),
        downloader_name=downloader_execution.name if downloader_execution is not None else "",
        downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
        download_dir=downloader_execution.download_dir if downloader_execution is not None else "",
        auto_import_enabled=True,
    )
    if pending_text == BT_SOURCE_UNSUPPORTED_TEXT:
        return pending_text
    return f"{association_text}\n\n{pending_text}"
