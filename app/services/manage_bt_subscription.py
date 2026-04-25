from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.db.bt_subscription_repo import BtSubscriptionItem, BtSubscriptionRepo
from app.services.add_to_downloader import AddToDownloaderService
from app.services.bt_candidate_scorer import BTCandidate, BTScoringContext, load_bt_scoring_rules, pick_best
from app.services.bt_subscription_command import (
    BT_SUBSCRIPTION_ADD_USAGE_TEXT,
    BT_SUBSCRIPTION_REMOVE_USAGE_TEXT,
    BT_SUBSCRIPTION_USAGE_TEXT,
    BtSubscriptionCommand,
    format_bt_subscription_add_result,
    format_bt_subscription_clear_result,
    format_bt_subscription_list,
    format_bt_subscription_remove_result,
    parse_bt_subscription_add_request,
    parse_bt_subscription_query as _parse_bt_subscription_query,
)
from app.services.bt_subscription_dispatch_support import dispatch_bt_subscription_item
from app.services.bt_subscription_last_seen_support import update_bt_subscription_last_seen
from app.services.bt_subscription_repo_support import (
    add_subscription_item,
    clear_subscription_items,
    list_subscription_chat_ids,
    list_subscription_items,
    remove_subscription_item,
)
from app.services.bt_subscription_scheduler_support import collect_bt_subscription_scheduler_notifications
from app.services.bt_subscription_scan_support import (
    BtSubscriptionRunResult,
    format_bt_subscription_run_result,
    scan_bt_subscription_items,
)
from app.services.bt_sources import resolve_bt_source

SearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
BT_SUBSCRIPTION_LIST_FAILED_TEXT = "BT 订阅清单读取失败，请稍后重试。"
BT_SUBSCRIPTION_ADD_FAILED_TEXT = "BT 订阅写入失败，请稍后重试。"
BT_SUBSCRIPTION_REMOVE_FAILED_TEXT = "BT 订阅删除失败，请稍后重试。"
BT_SUBSCRIPTION_CLEAR_FAILED_TEXT = "BT 订阅清单清空失败，请稍后重试。"
BT_SUBSCRIPTION_RUN_EMPTY_TEXT = "当前没有可扫描的 BT 订阅。"
BT_SUBSCRIPTION_RUN_FAILED_TEXT = "BT 订阅扫描失败，请稍后重试。"
BT_SUBSCRIPTION_PENDING_CREATION_FAILED_TEXT = "BT 订阅待确认状态写入失败，请稍后重试。"
BT_SUBSCRIPTION_RUN_DONE_TEMPLATE = "BT 订阅扫描完成：共扫描 {scanned} 条，命中新资源 {matched} 条。"
BT_SUBSCRIPTION_RUN_NO_NEW_TEMPLATE = "BT 订阅扫描完成：共扫描 {scanned} 条，当前没有新资源。"
BT_SUBSCRIPTION_PENDING_CREATION_WARNING_TEXT = (
    "注意：本轮有命中的 BT 订阅未能创建下载待确认。\n"
    "请检查 SQLite/approval_record 和 jobs 表写入是否正常，然后重新执行 btsub run。"
)
BT_SUBSCRIPTION_LAST_SEEN_UPDATE_WARNING_TEXT = (
    "注意：BT 订阅最近资源真相未更新，下次扫描可能重复命中同一资源。\n"
    "请检查 SQLite 是否可写、订阅条目是否仍存在，然后重新执行 btsub run。"
)
BT_SUBSCRIPTION_LAST_SEEN_ITEM_MISSING_WARNING_TEXT = (
    "注意：BT 订阅条目已不存在，本轮命中的下载待确认已经创建，但不会更新最近资源真相。\n"
    "请先确认是否有人删除了该条订阅；如仍需继续追踪，请重新添加后再执行 btsub run。"
)
BT_SUBSCRIPTION_ITEM_MISSING_AFTER_ADD_REASON = "bt_subscription_item missing after insert"
BT_SUBSCRIPTION_LAST_SEEN_RESULT_MISSING_REASON = "bt subscription last_seen update result missing"
parse_bt_subscription_query = _parse_bt_subscription_query


@dataclass(frozen=True, slots=True)
class BtSubscriptionDispatchContext:
    downloader_name: str
    downloader_type: str
    download_dir: str

class ManageBtSubscriptionService:
    def __init__(
        self,
        bt_subscription_repo: BtSubscriptionRepo,
        search_func: SearchFunc,
        add_to_downloader_service: AddToDownloaderService,
    ) -> None:
        self._bt_subscription_repo = bt_subscription_repo
        self._search_func = search_func
        self._add_to_downloader_service = add_to_downloader_service

    def handle(self, command: BtSubscriptionCommand, *, chat_id: int | None) -> str:
        if chat_id is None or chat_id <= 0:
            return BT_SUBSCRIPTION_USAGE_TEXT

        if command.action == "list":
            return self._list_text(chat_id=chat_id)
        if command.action == "add":
            return self._add_text(chat_id=chat_id, raw_title=command.arg)
        if command.action == "remove":
            return self._remove_text(chat_id=chat_id, item_ref=command.arg)
        if command.action == "clear":
            return self._clear_text(chat_id=chat_id)
        return BT_SUBSCRIPTION_USAGE_TEXT

    async def run_once(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        dispatch_context: BtSubscriptionDispatchContext,
    ) -> str:
        if chat_id is None or chat_id <= 0:
            return BT_SUBSCRIPTION_USAGE_TEXT

        result = await self._scan_chat_once(
            chat_id=chat_id,
            user_id=user_id,
            dispatch_context=dispatch_context,
        )
        if result is None:
            return BT_SUBSCRIPTION_RUN_FAILED_TEXT
        if result.pending_creation_failed and result.matched <= 0:
            return BT_SUBSCRIPTION_PENDING_CREATION_FAILED_TEXT
        if result.scanned <= 0:
            return BT_SUBSCRIPTION_RUN_EMPTY_TEXT
        return format_bt_subscription_run_result(
            result=result,
            run_done_template=BT_SUBSCRIPTION_RUN_DONE_TEMPLATE,
            run_no_new_template=BT_SUBSCRIPTION_RUN_NO_NEW_TEMPLATE,
            pending_creation_warning_text=BT_SUBSCRIPTION_PENDING_CREATION_WARNING_TEXT,
        )

    async def run_scheduler_tick(
        self,
        *,
        dispatch_context: BtSubscriptionDispatchContext,
    ) -> tuple[tuple[int, str], ...] | None:
        return await collect_bt_subscription_scheduler_notifications(
            list_chat_ids=lambda: list_subscription_chat_ids(
                repo=self._bt_subscription_repo,
                is_chat_list_row_corrupted_reason=_is_bt_subscription_chat_list_row_corrupted_reason,
            ),
            scan_chat=lambda chat_id: self._scan_chat_once(
                chat_id=chat_id,
                user_id=None,
                dispatch_context=dispatch_context,
            ),
            format_notification=lambda result: format_bt_subscription_run_result(
                result=result,
                run_done_template=BT_SUBSCRIPTION_RUN_DONE_TEMPLATE,
                run_no_new_template=BT_SUBSCRIPTION_RUN_NO_NEW_TEMPLATE,
                pending_creation_warning_text=BT_SUBSCRIPTION_PENDING_CREATION_WARNING_TEXT,
            ),
            log_chat_ids_failed=lambda reason: _log_bt_subscription_scan_chat_ids_failed(reason=reason),
            log_chat_ids_result_missing=lambda reason: _log_bt_subscription_scan_chat_ids_result_missing(
                reason=reason
            ),
            log_chat_ids_row_corrupted=lambda reason: _log_bt_subscription_scan_chat_ids_row_corrupted(
                reason=reason
            ),
        )

    def _list_text(self, *, chat_id: int) -> str:
        items = self._list_items(chat_id=chat_id)
        if items is None:
            return BT_SUBSCRIPTION_LIST_FAILED_TEXT
        return format_bt_subscription_list(items)

    def _add_text(self, *, chat_id: int, raw_title: str) -> str:
        parsed_request = parse_bt_subscription_add_request(raw_title)
        if parsed_request is None:
            return BT_SUBSCRIPTION_ADD_USAGE_TEXT

        created = self._add_item(
            chat_id=chat_id,
            title=parsed_request.title,
            year=parsed_request.year,
            media_kind=parsed_request.media_kind,
        )
        if created is None:
            return BT_SUBSCRIPTION_ADD_FAILED_TEXT
        item, is_created = created
        return format_bt_subscription_add_result(item, is_created=is_created)

    def _remove_text(self, *, chat_id: int, item_ref: str) -> str:
        cleaned_ref = item_ref.strip()
        if not cleaned_ref.isdigit():
            return BT_SUBSCRIPTION_REMOVE_USAGE_TEXT
        item_id = int(cleaned_ref)
        if item_id <= 0:
            return BT_SUBSCRIPTION_REMOVE_USAGE_TEXT
        removed = self._remove_item(chat_id=chat_id, item_id=item_id)
        if removed is None:
            return BT_SUBSCRIPTION_REMOVE_FAILED_TEXT
        return format_bt_subscription_remove_result(item_id, removed=removed)

    def _clear_text(self, *, chat_id: int) -> str:
        deleted = self._clear_items(chat_id=chat_id)
        if deleted is None:
            return BT_SUBSCRIPTION_CLEAR_FAILED_TEXT
        return format_bt_subscription_clear_result(deleted)

    def _add_item(
        self,
        *,
        chat_id: int,
        title: str,
        year: str,
        media_kind: str,
    ):
        result = add_subscription_item(
            repo=self._bt_subscription_repo,
            chat_id=chat_id,
            title=title,
            year=year,
            media_kind=media_kind,
            item_missing_reason=BT_SUBSCRIPTION_ITEM_MISSING_AFTER_ADD_REASON,
            is_item_row_corrupted_reason=_is_bt_subscription_item_row_corrupted_reason,
        )
        if result.ok:
            return result.value
        if result.status == "item_missing":
            _log_bt_subscription_add_item_missing_after_insert(
                chat_id=chat_id,
                title=title,
                year=year,
                media_kind=media_kind,
                reason=result.reason,
            )
            return None
        if result.status == "result_missing":
            _log_bt_subscription_add_result_missing(
                chat_id=chat_id,
                title=title,
                year=year,
                media_kind=media_kind,
                reason=result.reason,
            )
            return None
        if result.status == "row_corrupted":
            _log_bt_subscription_add_row_corrupted(
                chat_id=chat_id,
                title=title,
                year=year,
                media_kind=media_kind,
                reason=result.reason,
            )
            return None
        _log_bt_subscription_add_failed(
            chat_id=chat_id,
            title=title,
            year=year,
            media_kind=media_kind,
            reason=result.reason,
        )
        return None

    def _list_items(self, *, chat_id: int):
        result = list_subscription_items(
            repo=self._bt_subscription_repo,
            chat_id=chat_id,
            result_missing_reason="bt subscription list result missing",
            is_item_row_corrupted_reason=_is_bt_subscription_item_row_corrupted_reason,
        )
        if result.ok:
            return result.value
        if result.status == "result_missing":
            _log_bt_subscription_list_result_missing(chat_id=chat_id, reason=result.reason)
            return None
        if result.status == "row_corrupted":
            _log_bt_subscription_list_row_corrupted(chat_id=chat_id, reason=result.reason)
            return None
        _log_bt_subscription_list_failed(chat_id=chat_id, reason=result.reason)
        return None

    def _remove_item(self, *, chat_id: int, item_id: int):
        result = remove_subscription_item(
            repo=self._bt_subscription_repo,
            chat_id=chat_id,
            item_id=item_id,
            is_item_row_corrupted_reason=_is_bt_subscription_item_row_corrupted_reason,
        )
        if result.ok:
            return result.value
        if result.status == "result_missing":
            _log_bt_subscription_remove_result_missing(chat_id=chat_id, item_id=item_id, reason=result.reason)
            return None
        if result.status == "row_corrupted":
            _log_bt_subscription_remove_row_corrupted(chat_id=chat_id, item_id=item_id, reason=result.reason)
            return None
        _log_bt_subscription_remove_failed(chat_id=chat_id, item_id=item_id, reason=result.reason)
        return None

    def _clear_items(self, *, chat_id: int):
        result = clear_subscription_items(
            repo=self._bt_subscription_repo,
            chat_id=chat_id,
            is_item_row_corrupted_reason=_is_bt_subscription_item_row_corrupted_reason,
        )
        if result.ok:
            return result.value
        if result.status == "result_missing":
            _log_bt_subscription_clear_result_missing(chat_id=chat_id, reason=result.reason)
            return None
        if result.status == "row_corrupted":
            _log_bt_subscription_clear_row_corrupted(chat_id=chat_id, reason=result.reason)
            return None
        _log_bt_subscription_clear_failed(chat_id=chat_id, reason=result.reason)
        return None

    async def _run_for_item(
        self,
        *,
        item: BtSubscriptionItem,
        chat_id: int,
        user_id: int | None,
        dispatch_context: BtSubscriptionDispatchContext,
    ) -> tuple[str | None, bool]:
        result = await dispatch_bt_subscription_item(
            item=item,
            search_func=self._search_func,
            resolve_candidate=lambda results, resolved_item: self._resolve_item_dispatch_candidate(
                results=results,
                item=resolved_item,
            ),
            create_pending=lambda source, title: self._add_to_downloader_service.add_candidate_source(
                chat_id=chat_id,
                user_id=user_id,
                source=source,
                title=title,
                downloader_name=dispatch_context.downloader_name,
                downloader_type=dispatch_context.downloader_type,
                download_dir=dispatch_context.download_dir,
                auto_import_enabled=True,
            ),
            update_last_seen_status=lambda source, title: update_bt_subscription_last_seen(
                repo=self._bt_subscription_repo,
                chat_id=chat_id,
                item_id=item.item_id,
                source=source,
                title=title,
                item_missing_reason="bt_subscription_item missing during last_seen update",
                result_missing_reason=BT_SUBSCRIPTION_LAST_SEEN_RESULT_MISSING_REASON,
                is_item_row_corrupted_reason=_is_bt_subscription_item_row_corrupted_reason,
                log_item_missing=lambda reason: _log_bt_subscription_last_seen_item_missing(
                    item=item,
                    chat_id=chat_id,
                    source=source,
                    title=title,
                    reason=reason,
                ),
                log_result_missing=lambda reason: _log_bt_subscription_last_seen_result_missing(
                    item=item,
                    chat_id=chat_id,
                    source=source,
                    title=title,
                    reason=reason,
                ),
                log_row_corrupted=lambda reason: _log_bt_subscription_last_seen_row_corrupted(
                    item=item,
                    chat_id=chat_id,
                    source=source,
                    title=title,
                    reason=reason,
                ),
                log_update_failed=lambda reason: _log_bt_subscription_last_seen_update_failed(
                    item=item,
                    chat_id=chat_id,
                    source=source,
                    title=title,
                    reason=reason,
                ),
            ),
            log_scan_error=lambda query, error: _log_bt_subscription_scan_error(
                item=item,
                query=query,
                error=error,
            ),
            log_pending_creation_failed=lambda source, title, reason: _log_bt_subscription_pending_creation_failed(
                item=item,
                chat_id=chat_id,
                source=source,
                title=title,
                reason=reason,
            ),
            last_seen_update_warning_text=BT_SUBSCRIPTION_LAST_SEEN_UPDATE_WARNING_TEXT,
            last_seen_item_missing_warning_text=BT_SUBSCRIPTION_LAST_SEEN_ITEM_MISSING_WARNING_TEXT,
        )
        return result.reply, result.pending_creation_failed

    def _resolve_item_dispatch_candidate(
        self,
        *,
        results: Sequence[Mapping[str, Any]],
        item: BtSubscriptionItem,
    ) -> tuple[str, str] | None:
        selected_result = _pick_subscription_candidate(
            results,
            item=item,
            last_seen_source=item.last_seen_source,
        )
        if selected_result is None:
            return None
        selected_source = _resolve_candidate_source(selected_result)
        if not selected_source:
            return None
        candidate_title = _resolve_candidate_title(selected_result, item=item)
        return selected_source, candidate_title

    async def _scan_chat_once(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        dispatch_context: BtSubscriptionDispatchContext,
    ) -> BtSubscriptionRunResult | None:
        return await scan_bt_subscription_items(
            list_items=lambda: list_subscription_items(
                repo=self._bt_subscription_repo,
                chat_id=chat_id,
                result_missing_reason="bt subscription scan items result missing",
                is_item_row_corrupted_reason=_is_bt_subscription_item_row_corrupted_reason,
            ),
            run_for_item=lambda item: self._run_for_item(
                item=item,
                chat_id=chat_id,
                user_id=user_id,
                dispatch_context=dispatch_context,
            ),
            log_items_failed=lambda reason: _log_bt_subscription_scan_items_failed(chat_id=chat_id, reason=reason),
            log_items_result_missing=lambda reason: _log_bt_subscription_scan_items_result_missing(
                chat_id=chat_id,
                reason=reason,
            ),
            log_items_row_corrupted=lambda reason: _log_bt_subscription_scan_items_row_corrupted(
                chat_id=chat_id,
                reason=reason,
            ),
        )

def _pick_subscription_candidate(
    results: Sequence[Mapping[str, Any]],
    *,
    item: BtSubscriptionItem,
    last_seen_source: str,
) -> Mapping[str, Any] | None:
    candidate_pairs: list[tuple[BTCandidate, Mapping[str, Any]]] = []
    normalized_last_seen_source = last_seen_source.strip()
    for result in results:
        source = _resolve_candidate_source(result)
        if not source or source == normalized_last_seen_source:
            continue
        candidate = _build_subscription_bt_candidate(result, item=item)
        if candidate is not None:
            candidate_pairs.append((candidate, result))
    if not candidate_pairs:
        return None
    best = pick_best(
        [candidate for candidate, _ in candidate_pairs],
        BTScoringContext(query="", media_kind=item.media_kind),
        rules=load_bt_scoring_rules(),
    )
    if best is None:
        return None
    for candidate, result in candidate_pairs:
        if candidate is best.candidate:
            return result
    return None


def _resolve_candidate_source(candidate: Mapping[str, Any]) -> str:
    return resolve_bt_source(candidate)


def _resolve_candidate_title(candidate: Mapping[str, Any], *, item: BtSubscriptionItem) -> str:
    title = str(candidate.get("title", "")).strip()
    if title:
        return title
    year_text = item.year if item.year else "-"
    return f"{item.title} ({year_text})"


def _build_subscription_bt_candidate(result: Mapping[str, Any], *, item: BtSubscriptionItem) -> BTCandidate | None:
    source = _resolve_candidate_source(result)
    title = _resolve_candidate_title(result, item=item)
    if not source or not title:
        return None
    return BTCandidate(
        source_site=str(result.get("indexerName", "")).strip() or str(result.get("sourceProvider", "")).strip() or "unknown",
        title=title,
        magnet_or_torrent_url=source,
        size_bytes=_safe_optional_int(result.get("size")),
        seeders=_safe_optional_int(result.get("seeders")),
        leechers=_safe_optional_int(result.get("peers")),
        resolution=_extract_resolution(title),
        codec=_extract_codec(title),
        source_type=_extract_source_type(title),
        audio=(),
        release_group=_extract_release_group(title),
        age_days=None,
        media_kind=item.media_kind,
    )


def _extract_resolution(title: str) -> str | None:
    lowered_title = title.strip().lower()
    if re.search(r"\b(2160p|4k)\b", lowered_title):
        return "2160p"
    if re.search(r"\b1080p\b", lowered_title):
        return "1080p"
    if re.search(r"\b720p\b", lowered_title):
        return "720p"
    return None


def _extract_codec(title: str) -> str | None:
    lowered_title = title.strip().lower()
    if re.search(r"\b(x265|hevc)\b", lowered_title):
        return "x265" if "x265" in lowered_title else "HEVC"
    if re.search(r"\b(x264|avc)\b", lowered_title):
        return "x264"
    return None


def _extract_source_type(title: str) -> str | None:
    lowered_title = title.strip().lower()
    if "remux" in lowered_title:
        return "Remux"
    if "bluray" in lowered_title or "blu-ray" in lowered_title:
        return "BluRay"
    if "bdrip" in lowered_title:
        return "BDRip"
    if "web-dl" in lowered_title or "webdl" in lowered_title:
        return "WEB-DL"
    if "webrip" in lowered_title or "web-rip" in lowered_title:
        return "WEBRip"
    return None


def _extract_release_group(title: str) -> str | None:
    matched = re.search(r"-([A-Za-z0-9][A-Za-z0-9-]+)$", title.strip())
    if matched is None:
        return None
    return str(matched.group(1) or "").strip() or None


def _safe_optional_int(value: Any) -> int | None:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return None
    if resolved > 0:
        return resolved
    return None


def _log_bt_subscription_scan_error(
    *,
    item: BtSubscriptionItem,
    query: str,
    error: Exception,
) -> None:
    print(
        f"\033[31m[BT 订阅扫描失败]\033[0m 条目ID={item.item_id} 类型={item.media_kind} 查询={query} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 Prowlarr 地址、API Key 和网络连通性后重试。"
    )


def _log_bt_subscription_scan_items_failed(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅扫描读取失败]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可读，以及 bt_subscription_item 表是否正常。"
    )


def _log_bt_subscription_scan_items_result_missing(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅扫描结果缺失]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 查询返回是否仍带有完整列表；"
        "当前会停止本轮扫描，避免把缺失真相误判成“当前没有可扫描条目”。"
    )


def _log_bt_subscription_scan_items_row_corrupted(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅扫描记录损坏]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；"
        "当前会停止本轮扫描，避免把损坏记录误判成可继续自动追更的正常条目。"
    )


def _log_bt_subscription_scan_chat_ids_failed(*, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅扫描 chat 列表读取失败]\033[0m 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可读，以及 bt_subscription_item 表是否正常。"
    )


def _log_bt_subscription_scan_chat_ids_result_missing(*, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅扫描 chat 列表结果缺失]\033[0m 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item chat 列表查询返回是否仍带有完整结果；"
        "当前会停止 scheduler tick，避免把缺失真相误判成“当前没有订阅 chat”。"
    )


def _log_bt_subscription_scan_chat_ids_row_corrupted(*, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅扫描 chat 列表记录损坏]\033[0m 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 表里的 chat_id 真相字段；"
        "当前会停止 scheduler tick，避免把损坏记录误判成可继续扫描的订阅 chat。"
    )


def _log_bt_subscription_list_failed(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅清单读取失败]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可读，以及 bt_subscription_item 表是否正常。"
    )


def _log_bt_subscription_list_result_missing(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅清单结果缺失]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 查询返回是否仍带有完整列表；"
        "当前会按读取失败处理，避免把缺失真相误判成“清单为空”。"
    )


def _log_bt_subscription_list_row_corrupted(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅清单记录损坏]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；"
        "当前会按读取失败处理，避免把损坏记录误判成正常订阅清单。"
    )


def _log_bt_subscription_remove_failed(*, chat_id: int, item_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅删除失败]\033[0m chat_id={chat_id} item_id={item_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写，以及 bt_subscription_item 表和当前条目是否正常。"
    )


def _log_bt_subscription_remove_result_missing(*, chat_id: int, item_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅删除结果缺失]\033[0m chat_id={chat_id} item_id={item_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 删除查询返回是否仍带有完整结果；"
        "当前会按删除失败处理，避免把缺失真相误判成“条目不存在”。"
    )


def _log_bt_subscription_remove_row_corrupted(*, chat_id: int, item_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅删除命中坏记录]\033[0m chat_id={chat_id} item_id={item_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；"
        "当前会按删除失败处理，避免把损坏记录误判成可正常删除或“条目不存在”。"
    )


def _log_bt_subscription_clear_failed(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅清单清空失败]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写，以及 bt_subscription_item 表是否正常。"
    )


def _log_bt_subscription_clear_result_missing(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅清单清空结果缺失]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 清空查询返回是否仍带有完整结果；"
        "当前会按清空失败处理，避免把缺失真相误判成“清单本来就是空的”。"
    )


def _log_bt_subscription_clear_row_corrupted(*, chat_id: int, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅清单清空命中坏记录]\033[0m chat_id={chat_id} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；"
        "当前会按清空失败处理，避免把损坏记录误判成可正常清空或“清单本来就是空的”。"
    )


def _log_bt_subscription_add_failed(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅写入失败]\033[0m chat_id={chat_id} title={title} year={year or '-'} "
        f"media_kind={media_kind} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写，以及 bt_subscription_item 表和当前条目是否正常。"
    )


def _log_bt_subscription_add_result_missing(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅写入结果缺失]\033[0m chat_id={chat_id} title={title} year={year or '-'} "
        f"media_kind={media_kind} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 插入查询返回是否仍带有完整结果；"
        "当前会按写入失败处理，避免把缺失真相误判成“已成功添加”。"
    )


def _log_bt_subscription_add_item_missing_after_insert(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅写入后条目缺失]\033[0m chat_id={chat_id} title={title} year={year or '-'} "
        f"media_kind={media_kind} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 表是否被并发删除或触发器回滚；"
        "如需继续添加，请先确认 SQLite 写入后能立即回读该条目。"
    )


def _log_bt_subscription_add_row_corrupted(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅写入命中坏记录]\033[0m chat_id={chat_id} title={title} year={year or '-'} "
        f"media_kind={media_kind} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；"
        "当前会按写入失败处理，避免把损坏记录误判成可复用旧条目或成功新建条目。"
    )


def _log_bt_subscription_last_seen_update_failed(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅最近资源回写失败]\033[0m chat_id={chat_id} 条目ID={item.item_id} "
        f"类型={item.media_kind} source={source} title={title} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可写、订阅条目是否仍存在，然后重新执行 btsub run。"
    )


def _log_bt_subscription_last_seen_item_missing(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅最近资源回写条目缺失]\033[0m chat_id={chat_id} 条目ID={item.item_id} "
        f"类型={item.media_kind} source={source} title={title} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查该订阅条目是否已被删除；如仍需继续追踪，请重新添加后再执行 btsub run。"
    )


def _log_bt_subscription_last_seen_result_missing(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅最近资源回写结果缺失]\033[0m chat_id={chat_id} 条目ID={item.item_id} "
        f"类型={item.media_kind} source={source} title={title} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 更新返回是否仍带有明确结果；"
        "当前会保留已创建的下载待确认，并提示最近资源真相未更新，避免把持久化缺口误判成普通成功。"
    )


def _log_bt_subscription_last_seen_row_corrupted(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅最近资源回写命中坏记录]\033[0m chat_id={chat_id} 条目ID={item.item_id} "
        f"类型={item.media_kind} source={source} title={title} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；"
        "当前会保留已创建的下载待确认，并提示最近资源真相未更新，避免把损坏记录误判成普通回写失败。"
    )


def _log_bt_subscription_pending_creation_failed(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[BT 订阅待确认创建失败]\033[0m chat_id={chat_id} 条目ID={item.item_id} "
        f"类型={item.media_kind} source={source} title={title} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 和 jobs 表写入是否正常，然后重新执行 btsub run。"
    )

def _is_bt_subscription_item_row_corrupted_reason(reason: str) -> bool:
    return reason in {
        "bt_subscription_item row identity corrupted after read",
        "bt_subscription_item media kind corrupted after read",
    }


def _is_bt_subscription_chat_list_row_corrupted_reason(reason: str) -> bool:
    return reason == "bt_subscription_item chat identity corrupted in chat list after read"
