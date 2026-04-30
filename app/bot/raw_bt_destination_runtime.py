from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

from app.bot.bt_pending_runtime import (
    BT_PENDING_CLEAR_RESULT_MISSING_REASON,
    BT_PENDING_MISSING_AFTER_UPSERT_REASON,
    deserialize_bt_pending_payload as _deserialize_bt_pending_payload,
    is_bt_pending_row_corrupted_reason as _is_bt_pending_row_corrupted_reason,
    log_bt_pending_clear_failed as _log_bt_pending_clear_failed,
    log_bt_pending_clear_result_missing as _log_bt_pending_clear_result_missing,
    log_bt_pending_missing_after_upsert as _log_bt_pending_missing_after_upsert,
    log_bt_pending_payload_corruption as _log_bt_pending_payload_corruption,
    log_bt_pending_persist_failed as _log_bt_pending_persist_failed,
    log_bt_pending_read_failed as _log_bt_pending_read_failed,
    log_bt_pending_row_corrupted as _log_bt_pending_row_corrupted,
    resolve_bt_pending_repo as _resolve_bt_pending_repo,
    serialize_bt_pending_payload as _serialize_bt_pending_payload,
)
from app.config import RawBtDestinationOption
from app.db.bt_pending_repo import (
    BT_PENDING_STAGE_RAW_BT_DESTINATION,
    BtPendingPersistenceError,
)
from app.operational_logging import emit_operational_log
from app.services.add_to_downloader import BT_SOURCE_UNSUPPORTED_TEXT, AddToDownloaderService
from app.services.pure_bt import extract_bt_search_query, pick_single_item_candidate
from app.services.search_media import SearchMediaService

RAW_BT_DESTINATION_PROMPT_TEXT_TEMPLATE = (
    "已记录本次 BT 分类：其他 BT 资源（raw_bt）。\n"
    "请选择预设目标目录：\n"
    "{options}\n"
    "请回复目录编号或目录键，例如：1 或 downloads\n"
    "当前这一步只记录目录 follow-up，不会执行下载投递。\n"
    "\n"
    "下一步\n"
    "{actions}"
)
RAW_BT_DESTINATION_PENDING_REMINDER_TEMPLATE = (
    "当前正在等待 raw_bt 目标目录。\n"
    "请回复目录编号或目录键，例如：{example}\n"
    "\n"
    "下一步\n"
    "{actions}"
)
RAW_BT_DESTINATION_SELECTED_TEMPLATE = (
    "已记录 raw_bt 目标目录。\n"
    "目录键: {key}\n"
    "目录说明: {label}\n"
    "目标路径: {target_dir}"
)
RAW_BT_DESTINATION_CANCELLED_TEXT = "已取消当前 raw_bt 目录选择，请重新发送磁力或 BT 指令。"
RAW_BT_DESTINATION_INVALID_TEMPLATE = (
    "未识别到有效的 raw_bt 目录选项：{query}\n"
    "请回复目录编号或目录键，例如：{example}\n"
    "可选目录：\n"
    "{options}\n"
    "\n"
    "下一步\n"
    "{actions}"
)
RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT = "raw_bt 目录选择未就绪，请先配置预设目标目录后重试。"
PURE_BT_CANDIDATE_SELECTED_TEMPLATE = (
    "pure BT 最小优选已命中单片资源。\n"
    "搜索词: {query}\n"
    "命中资源: {title}"
)
RAW_BT_DESTINATION_PENDING_BY_CHAT_KEY = "raw_bt_destination_pending_by_chat"


@dataclass(frozen=True, slots=True)
class RawBtDestinationPending:
    options: tuple[RawBtDestinationOption, ...]
    source: str


class ResolvedDownloaderExecutionLike(Protocol):
    name: str
    downloader_type: str


def log_pure_bt_search_error(*, query: str, error: httpx.HTTPError | ValueError) -> None:
    emit_operational_log(
        title="pure BT 搜索失败",
        detail=f"查询={query} 原因={error}",
        fix_hint="检查 Prowlarr 地址、API Key 和网络连通性后重试。",
    )


def _resolve_raw_bt_destination_pending_by_chat(
    bot_data: MutableMapping[str, object],
) -> dict[int, RawBtDestinationPending]:
    pending_by_chat = bot_data.get(RAW_BT_DESTINATION_PENDING_BY_CHAT_KEY)
    if isinstance(pending_by_chat, dict):
        return pending_by_chat
    resolved_pending_by_chat: dict[int, RawBtDestinationPending] = {}
    bot_data[RAW_BT_DESTINATION_PENDING_BY_CHAT_KEY] = resolved_pending_by_chat
    return resolved_pending_by_chat


def set_raw_bt_destination_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    options: tuple[RawBtDestinationOption, ...],
    source: str,
    bt_pending_repo_key: str = "bt_pending_repo",
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_raw_bt_destination_pending_by_chat(bot_data)
    pending_by_chat[chat_id] = RawBtDestinationPending(options=options, source=source.strip())
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return True
    try:
        pending_repo.upsert_pending(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
            payload_json=_serialize_bt_pending_payload(
                {
                    "options": [
                        {
                            "key": option.key,
                            "label": option.label,
                            "target_dir": option.target_dir,
                        }
                        for option in options
                    ],
                    "source": source.strip(),
                }
            ),
        )
    except BtPendingPersistenceError as error:
        if str(error) == BT_PENDING_MISSING_AFTER_UPSERT_REASON:
            _log_bt_pending_missing_after_upsert(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_persist_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
                reason=str(error),
            )
        pending_by_chat.pop(chat_id, None)
        return False
    except sqlite3.Error as error:
        _log_bt_pending_persist_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
            reason=str(error),
        )
        pending_by_chat.pop(chat_id, None)
        return False
    return True


def get_raw_bt_destination_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    bt_pending_repo_key: str = "bt_pending_repo",
) -> RawBtDestinationPending | None | Literal[False]:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_raw_bt_destination_pending_by_chat(bot_data)
    pending = pending_by_chat.get(chat_id)
    if isinstance(pending, RawBtDestinationPending):
        return pending
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return None
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except (BtPendingPersistenceError, sqlite3.Error) as error:
        if _is_bt_pending_row_corrupted_reason(str(error)):
            _log_bt_pending_row_corrupted(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_read_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
                reason=str(error),
            )
        return False
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_RAW_BT_DESTINATION:
        return None
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return False
    raw_options = payload.get("options")
    source = str(payload.get("source", "")).strip()
    if not source:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.source missing",
        )
        return False
    if not isinstance(raw_options, list):
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.options missing or not list",
        )
        return False
    options: list[RawBtDestinationOption] = []
    for raw_option in raw_options:
        if not isinstance(raw_option, dict):
            continue
        key = str(raw_option.get("key", "")).strip()
        label = str(raw_option.get("label", "")).strip()
        target_dir = str(raw_option.get("target_dir", "")).strip()
        if not key or not label or not target_dir:
            continue
        options.append(RawBtDestinationOption(key=key, label=label, target_dir=target_dir))
    if not options:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.options has no valid entries",
        )
        return False
    resolved_pending = RawBtDestinationPending(options=tuple(options), source=source)
    pending_by_chat[chat_id] = resolved_pending
    return resolved_pending


def clear_raw_bt_destination_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    bt_pending_repo_key: str = "bt_pending_repo",
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_raw_bt_destination_pending_by_chat(bot_data)
    pending = pending_by_chat.pop(chat_id, None)
    cleared = pending is not None
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return cleared
    try:
        cleared_result = pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_RAW_BT_DESTINATION)
        if cleared_result is None:
            raise BtPendingPersistenceError(BT_PENDING_CLEAR_RESULT_MISSING_REASON)
        return cleared_result or cleared
    except (BtPendingPersistenceError, sqlite3.Error) as error:
        if str(error) == BT_PENDING_CLEAR_RESULT_MISSING_REASON:
            _log_bt_pending_clear_result_missing(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_clear_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
                reason=str(error),
            )
        if pending is not None:
            pending_by_chat[chat_id] = pending
        return None


def enter_pure_bt_flow(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    source: str,
    raw_bt_destination_options_key: str,
    bt_pending_repo_key: str = "bt_pending_repo",
    raw_bt_destination_service_not_ready_text: str = RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT,
    service_not_ready_text: str,
) -> str:
    options = bot_data.get(raw_bt_destination_options_key)
    if not isinstance(options, tuple) or not all(isinstance(option, RawBtDestinationOption) for option in options):
        return raw_bt_destination_service_not_ready_text
    if not options:
        return raw_bt_destination_service_not_ready_text
    if not set_raw_bt_destination_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        options=options,
        source=source,
        bt_pending_repo_key=bt_pending_repo_key,
    ):
        return service_not_ready_text
    return format_raw_bt_destination_prompt(options)


def can_dispatch_bt_source(source: str) -> bool:
    return source.strip().lower().startswith("magnet:?")


def format_raw_bt_destination_options(options: tuple[RawBtDestinationOption, ...]) -> str:
    lines: list[str] = []
    for index, option in enumerate(options, start=1):
        lines.append(f"{index}. {option.label} [{option.key}] -> {option.target_dir}")
    return "\n".join(lines) if lines else "- 暂无可用目录。"


def format_raw_bt_destination_prompt(options: tuple[RawBtDestinationOption, ...]) -> str:
    return RAW_BT_DESTINATION_PROMPT_TEXT_TEMPLATE.format(
        options=format_raw_bt_destination_options(options),
        actions=format_raw_bt_destination_actions(options),
    )


def resolve_raw_bt_destination_example(options: tuple[RawBtDestinationOption, ...]) -> str:
    if not options:
        return "downloads"
    first_option = options[0]
    return first_option.key or "1"


def format_raw_bt_destination_selected(option: RawBtDestinationOption) -> str:
    return RAW_BT_DESTINATION_SELECTED_TEMPLATE.format(
        key=option.key,
        label=option.label,
        target_dir=option.target_dir,
    )


def parse_raw_bt_destination_choice(
    query: str,
    options: tuple[RawBtDestinationOption, ...],
) -> RawBtDestinationOption | None:
    normalized_text = query.strip().lower()
    if not normalized_text:
        return None
    if normalized_text.isdigit():
        index = int(normalized_text)
        if 1 <= index <= len(options):
            return options[index - 1]
    for option in options:
        if normalized_text == option.key.lower():
            return option
    return None


def format_raw_bt_destination_invalid(
    query: str,
    options: tuple[RawBtDestinationOption, ...],
) -> str:
    return RAW_BT_DESTINATION_INVALID_TEMPLATE.format(
        query=query.strip(),
        example=resolve_raw_bt_destination_example(options),
        options=format_raw_bt_destination_options(options),
        actions=format_raw_bt_destination_actions(options),
    )


def format_raw_bt_destination_actions(options: tuple[RawBtDestinationOption, ...]) -> str:
    lines: list[str] = []
    for option in options:
        lines.append(f"{option.label}：发送 {option.key}")
    return "\n".join(lines) if lines else "暂无可用目录。"


def _resolve_search_candidate_source(candidate: Mapping[str, object]) -> str:
    for key in ("downloadUrl", "downloadurl", "magnetUrl", "magneturl", "guid"):
        value = candidate.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


async def handle_raw_bt_destination_query(
    *,
    query: str,
    pending: RawBtDestinationPending,
    chat_id: int | None,
    user_id: int | None,
    bot_data: MutableMapping[str, object],
    add_to_downloader_service_key: str,
    search_service_key: str,
    clear_pending: Callable[[], bool | None],
    resolve_downloader_execution: Callable[[], tuple[ResolvedDownloaderExecutionLike | None, str | None]],
    log_pure_bt_search_error: Callable[[str, httpx.HTTPError | ValueError], None],
    service_not_ready_text: str,
    bt_source_required_text: str,
    pure_bt_search_failed_text: str,
    pure_bt_candidate_selected_template: str,
    pure_bt_candidate_not_found_template: str,
) -> str:
    if chat_id is None:
        return service_not_ready_text
    selected_option = parse_raw_bt_destination_choice(query, pending.options)
    if selected_option is None:
        return format_raw_bt_destination_invalid(query, pending.options)

    cleared_raw_bt_destination = clear_pending()
    if cleared_raw_bt_destination is None:
        return service_not_ready_text
    selected_text = format_raw_bt_destination_selected(selected_option)
    add_service = bot_data.get(add_to_downloader_service_key)
    if not isinstance(add_service, AddToDownloaderService):
        return service_not_ready_text
    downloader_execution, resolution_error = resolve_downloader_execution()
    if resolution_error is not None:
        return resolution_error
    if can_dispatch_bt_source(pending.source):
        pending_text = await add_service.add_bt_source(
            chat_id=chat_id,
            user_id=user_id,
            source=pending.source,
            title=f"raw_bt -> {selected_option.label}",
            downloader_name=downloader_execution.name if downloader_execution is not None else "",
            downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
            download_dir=selected_option.target_dir,
            auto_import_enabled=False,
        )
        if pending_text == BT_SOURCE_UNSUPPORTED_TEXT:
            return pending_text
        return f"{selected_text}\n\n{pending_text}"

    pure_bt_query = extract_bt_search_query(pending.source)
    if not pure_bt_query:
        return f"{selected_text}\n\n{bt_source_required_text}"

    search_service = bot_data.get(search_service_key)
    if not isinstance(search_service, SearchMediaService):
        return service_not_ready_text
    try:
        raw_results = await search_service.search_raw_candidates(pure_bt_query)
    except (httpx.HTTPError, ValueError) as error:
        log_pure_bt_search_error(pure_bt_query, error)
        return f"{selected_text}\n\n{pure_bt_search_failed_text}"

    selected_candidate = pick_single_item_candidate(raw_results, query=pure_bt_query)
    if selected_candidate is None:
        return f"{selected_text}\n\n{pure_bt_candidate_not_found_template.format(query=pure_bt_query)}"

    candidate_source = _resolve_search_candidate_source(selected_candidate)
    candidate_title = str(selected_candidate.get("title", "")).strip() or pure_bt_query
    pending_text = await add_service.add_candidate_source(
        chat_id=chat_id,
        user_id=user_id,
        source=candidate_source,
        title=candidate_title,
        downloader_name=downloader_execution.name if downloader_execution is not None else "",
        downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
        download_dir=selected_option.target_dir,
        auto_import_enabled=False,
    )
    return (
        f"{selected_text}\n\n"
        f"{pure_bt_candidate_selected_template.format(query=pure_bt_query, title=candidate_title)}\n\n"
        f"{pending_text}"
    )
