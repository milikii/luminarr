from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from app.operational_logging import emit_operational_log
from app.db.bt_subscription_repo import BtSubscriptionItem, BtSubscriptionRepo
from app.services.add_to_downloader import ADD_PENDING_STATE_UNAVAILABLE_TEXT, AddToDownloaderService
from app.services.bt_subscription_candidate_helpers import (
    pick_subscription_candidate,
    resolve_candidate_source,
    resolve_candidate_title,
)
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
)
from app.services.bt_subscription_repo_support import (
    BtSubscriptionRepoResult,
    add_subscription_item,
    clear_subscription_items,
    list_subscription_chat_ids,
    list_subscription_items,
    remove_subscription_item,
    update_subscription_last_seen,
)
from app.services.media_item_display import format_title_year
from app.services.media_kind import media_kind_label

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

@dataclass(frozen=True, slots=True)
class BtSubscriptionRunResult:
    scanned: int
    matched: int
    replies: tuple[str, ...]
    pending_creation_failed: bool = False


LogSubscriptionLastSeenReasonFunc = Callable[[str], None]
ListSubscriptionItemsFunc = Callable[[], BtSubscriptionRepoResult[Sequence[BtSubscriptionItem]]]
RunSubscriptionItemFunc = Callable[[BtSubscriptionItem], Awaitable[tuple[str | None, bool]]]
LogSubscriptionScanItemsReasonFunc = Callable[[str], None]
SearchSubscriptionResultsFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
ResolveSubscriptionCandidateFunc = Callable[[Sequence[Mapping[str, Any]], BtSubscriptionItem], tuple[str, str] | None]
CreateSubscriptionPendingFunc = Callable[[str, str], Awaitable[str]]
UpdateSubscriptionLastSeenStatusFunc = Callable[[str, str], str]
LogSubscriptionScanErrorFunc = Callable[[str, Exception], None]
LogSubscriptionPendingCreationFailedFunc = Callable[[str, str, str], None]
ListSubscriptionChatIdsFunc = Callable[[], BtSubscriptionRepoResult[Sequence[int]]]
ScanSubscriptionChatFunc = Callable[[int], Awaitable[BtSubscriptionRunResult | None]]
FormatSubscriptionNotificationFunc = Callable[[BtSubscriptionRunResult], str]
LogSubscriptionSchedulerReasonFunc = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class BtSubscriptionDispatchContext:
    downloader_name: str
    downloader_type: str
    download_dir: str


@dataclass(frozen=True, slots=True)
class BtSubscriptionItemDispatchResult:
    reply: str | None
    pending_creation_failed: bool = False


def update_bt_subscription_last_seen(
    *,
    repo: BtSubscriptionRepo,
    chat_id: int,
    item_id: int,
    source: str,
    title: str,
    item_missing_reason: str,
    result_missing_reason: str,
    is_item_row_corrupted_reason: Callable[[str], bool],
    log_item_missing: LogSubscriptionLastSeenReasonFunc,
    log_result_missing: LogSubscriptionLastSeenReasonFunc,
    log_row_corrupted: LogSubscriptionLastSeenReasonFunc,
    log_update_failed: LogSubscriptionLastSeenReasonFunc,
) -> str:
    result = update_subscription_last_seen(
        repo=repo,
        chat_id=chat_id,
        item_id=item_id,
        source=source,
        title=title,
        item_missing_reason=item_missing_reason,
        result_missing_reason=result_missing_reason,
        is_item_row_corrupted_reason=is_item_row_corrupted_reason,
    )
    if result.ok:
        return "updated"
    if result.status == "item_missing":
        log_item_missing(result.reason)
        return "item_missing"
    if result.status == "result_missing":
        log_result_missing(result.reason)
        return "persistence_failed"
    if result.status == "row_corrupted":
        log_row_corrupted(result.reason)
        return "persistence_failed"
    log_update_failed(result.reason)
    return "persistence_failed"


async def collect_bt_subscription_scheduler_notifications(
    *,
    list_chat_ids: ListSubscriptionChatIdsFunc,
    scan_chat: ScanSubscriptionChatFunc,
    format_notification: FormatSubscriptionNotificationFunc,
    log_chat_ids_failed: LogSubscriptionSchedulerReasonFunc,
    log_chat_ids_result_missing: LogSubscriptionSchedulerReasonFunc,
    log_chat_ids_row_corrupted: LogSubscriptionSchedulerReasonFunc,
) -> tuple[tuple[int, str], ...] | None:
    chat_ids_result = list_chat_ids()
    if not chat_ids_result.ok:
        if chat_ids_result.status == "result_missing":
            log_chat_ids_result_missing(chat_ids_result.reason)
        elif chat_ids_result.status == "row_corrupted":
            log_chat_ids_row_corrupted(chat_ids_result.reason)
        else:
            log_chat_ids_failed(chat_ids_result.reason)
        return None

    notifications: list[tuple[int, str]] = []
    scan_failed = False
    for chat_id in chat_ids_result.value or ():
        result = await scan_chat(chat_id)
        if result is None:
            scan_failed = True
            continue
        if result.pending_creation_failed and result.matched <= 0:
            scan_failed = True
            continue
        if result.matched <= 0:
            continue
        notifications.append((chat_id, format_notification(result)))
    if scan_failed and not notifications:
        return None
    return tuple(notifications)


async def scan_bt_subscription_items(
    *,
    list_items: ListSubscriptionItemsFunc,
    run_for_item: RunSubscriptionItemFunc,
    log_items_failed: LogSubscriptionScanItemsReasonFunc,
    log_items_result_missing: LogSubscriptionScanItemsReasonFunc,
    log_items_row_corrupted: LogSubscriptionScanItemsReasonFunc,
) -> BtSubscriptionRunResult | None:
    items_result = list_items()
    if not items_result.ok:
        if items_result.status == "result_missing":
            log_items_result_missing(items_result.reason)
        elif items_result.status == "row_corrupted":
            log_items_row_corrupted(items_result.reason)
        else:
            log_items_failed(items_result.reason)
        return None

    items = items_result.value or ()
    if not items:
        return BtSubscriptionRunResult(scanned=0, matched=0, replies=())

    replies: list[str] = []
    matched = 0
    pending_creation_failed = False
    for item in items:
        reply, item_pending_creation_failed = await run_for_item(item)
        pending_creation_failed = pending_creation_failed or item_pending_creation_failed
        if reply is None:
            continue
        matched += 1
        replies.append(reply)
    return BtSubscriptionRunResult(
        scanned=len(items),
        matched=matched,
        replies=tuple(replies),
        pending_creation_failed=pending_creation_failed,
    )


def format_bt_subscription_run_result(
    *,
    result: BtSubscriptionRunResult,
    run_done_template: str,
    run_no_new_template: str,
    pending_creation_warning_text: str,
) -> str:
    header = (
        run_done_template.format(scanned=result.scanned, matched=result.matched)
        if result.matched > 0
        else run_no_new_template.format(scanned=result.scanned)
    )
    if not result.replies:
        return header
    body = "\n\n".join(result.replies)
    if result.pending_creation_failed:
        body = f"{body}\n\n{pending_creation_warning_text}"
    return f"{header}\n\n{body}"


async def dispatch_bt_subscription_item(
    *,
    item: BtSubscriptionItem,
    search_func: SearchSubscriptionResultsFunc,
    resolve_candidate: ResolveSubscriptionCandidateFunc,
    create_pending: CreateSubscriptionPendingFunc,
    update_last_seen_status: UpdateSubscriptionLastSeenStatusFunc,
    log_scan_error: LogSubscriptionScanErrorFunc,
    log_pending_creation_failed: LogSubscriptionPendingCreationFailedFunc,
    last_seen_update_warning_text: str,
    last_seen_item_missing_warning_text: str,
) -> BtSubscriptionItemDispatchResult:
    query = _build_subscription_query(item)
    try:
        results = await search_func(query)
    except (httpx.HTTPError, ValueError) as error:
        log_scan_error(query, error)
        return BtSubscriptionItemDispatchResult(reply=None)

    resolved_candidate = resolve_candidate(results, item)
    if resolved_candidate is None:
        return BtSubscriptionItemDispatchResult(reply=None)
    selected_source, candidate_title = resolved_candidate

    pending_text = await create_pending(selected_source, candidate_title)
    if pending_text == ADD_PENDING_STATE_UNAVAILABLE_TEXT:
        log_pending_creation_failed(selected_source, candidate_title, pending_text)
        return BtSubscriptionItemDispatchResult(reply=None, pending_creation_failed=True)
    if "下载待确认：" not in pending_text:
        return BtSubscriptionItemDispatchResult(reply=None)

    reply = (
        f"BT 订阅命中新资源：{format_title_year(item.title, item.year)}\n"
        f"类型: {media_kind_label(item.media_kind)}\n"
        f"命中资源: {candidate_title}\n\n"
        f"{pending_text}"
    )
    last_seen_status = update_last_seen_status(selected_source, candidate_title)
    if last_seen_status == "updated":
        return BtSubscriptionItemDispatchResult(reply=reply)
    if last_seen_status == "item_missing":
        return BtSubscriptionItemDispatchResult(
            reply=f"{reply}\n\n{last_seen_item_missing_warning_text}",
        )
    return BtSubscriptionItemDispatchResult(
        reply=f"{reply}\n\n{last_seen_update_warning_text}",
    )


def _build_subscription_query(item: BtSubscriptionItem) -> str:
    title = item.title.strip()
    year = item.year.strip()
    if title and year:
        return f"{title} {year}"
    return title


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
        selected_result = pick_subscription_candidate(
            results,
            item=item,
            last_seen_source=item.last_seen_source,
        )
        if selected_result is None:
            return None
        selected_source = resolve_candidate_source(selected_result)
        if not selected_source:
            return None
        candidate_title = resolve_candidate_title(selected_result, item=item)
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


def _log_bt_subscription_scan_error(
    *,
    item: BtSubscriptionItem,
    query: str,
    error: Exception,
) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅扫描失败",
        context=f"条目ID={item.item_id} 类型={item.media_kind} 查询={query} 原因={error}",
        fix_hint="检查 Prowlarr 地址、API Key 和网络连通性后重试。",
    )


def _log_bt_subscription_scan_items_failed(*, chat_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅扫描读取失败",
        context=f"chat_id={chat_id} 原因={reason}",
        fix_hint="检查 SQLite 是否可读，以及 bt_subscription_item 表是否正常。",
    )


def _log_bt_subscription_scan_items_result_missing(*, chat_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅扫描结果缺失",
        context=f"chat_id={chat_id} 原因={reason}",
        fix_hint="检查 bt_subscription_item 查询返回是否仍带有完整列表；当前会停止本轮扫描，避免把缺失真相误判成“当前没有可扫描条目”。",
    )


def _log_bt_subscription_scan_items_row_corrupted(*, chat_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅扫描记录损坏",
        context=f"chat_id={chat_id} 原因={reason}",
        fix_hint="检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；当前会停止本轮扫描，避免把损坏记录误判成可继续自动追更的正常条目。",
    )


def _log_bt_subscription_scan_chat_ids_failed(*, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅扫描 chat 列表读取失败",
        context=f"原因={reason}",
        fix_hint="检查 SQLite 是否可读，以及 bt_subscription_item 表是否正常。",
    )


def _log_bt_subscription_scan_chat_ids_result_missing(*, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅扫描 chat 列表结果缺失",
        context=f"原因={reason}",
        fix_hint="检查 bt_subscription_item chat 列表查询返回是否仍带有完整结果；当前会停止 scheduler tick，避免把缺失真相误判成“当前没有订阅 chat”。",
    )


def _log_bt_subscription_scan_chat_ids_row_corrupted(*, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅扫描 chat 列表记录损坏",
        context=f"原因={reason}",
        fix_hint="检查 bt_subscription_item 表里的 chat_id 真相字段；当前会停止 scheduler tick，避免把损坏记录误判成可继续扫描的订阅 chat。",
    )


def _log_bt_subscription_list_failed(*, chat_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅清单读取失败",
        context=f"chat_id={chat_id} 原因={reason}",
        fix_hint="检查 SQLite 是否可读，以及 bt_subscription_item 表是否正常。",
    )


def _log_bt_subscription_list_result_missing(*, chat_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅清单结果缺失",
        context=f"chat_id={chat_id} 原因={reason}",
        fix_hint="检查 bt_subscription_item 查询返回是否仍带有完整列表；当前会按读取失败处理，避免把缺失真相误判成“清单为空”。",
    )


def _log_bt_subscription_list_row_corrupted(*, chat_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅清单记录损坏",
        context=f"chat_id={chat_id} 原因={reason}",
        fix_hint="检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；当前会按读取失败处理，避免把损坏记录误判成正常订阅清单。",
    )


def _log_bt_subscription_remove_failed(*, chat_id: int, item_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅删除失败",
        context=f"chat_id={chat_id} item_id={item_id} 原因={reason}",
        fix_hint="检查 SQLite 是否可写，以及 bt_subscription_item 表和当前条目是否正常。",
    )


def _log_bt_subscription_remove_result_missing(*, chat_id: int, item_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅删除结果缺失",
        context=f"chat_id={chat_id} item_id={item_id} 原因={reason}",
        fix_hint="检查 bt_subscription_item 删除查询返回是否仍带有完整结果；当前会按删除失败处理，避免把缺失真相误判成“条目不存在”。",
    )


def _log_bt_subscription_remove_row_corrupted(*, chat_id: int, item_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅删除命中坏记录",
        context=f"chat_id={chat_id} item_id={item_id} 原因={reason}",
        fix_hint="检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；当前会按删除失败处理，避免把损坏记录误判成可正常删除或“条目不存在”。",
    )


def _log_bt_subscription_clear_failed(*, chat_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅清单清空失败",
        context=f"chat_id={chat_id} 原因={reason}",
        fix_hint="检查 SQLite 是否可写，以及 bt_subscription_item 表是否正常。",
    )


def _log_bt_subscription_clear_result_missing(*, chat_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅清单清空结果缺失",
        context=f"chat_id={chat_id} 原因={reason}",
        fix_hint="检查 bt_subscription_item 清空查询返回是否仍带有完整结果；当前会按清空失败处理，避免把缺失真相误判成“清单本来就是空的”。",
    )


def _log_bt_subscription_clear_row_corrupted(*, chat_id: int, reason: str) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅清单清空命中坏记录",
        context=f"chat_id={chat_id} 原因={reason}",
        fix_hint="检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；当前会按清空失败处理，避免把损坏记录误判成可正常清空或“清单本来就是空的”。",
    )


def _log_bt_subscription_add_failed(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅写入失败",
        context=f"chat_id={chat_id} title={title} year={year or '-'} media_kind={media_kind} 原因={reason}",
        fix_hint="检查 SQLite 是否可写，以及 bt_subscription_item 表和当前条目是否正常。",
    )


def _log_bt_subscription_add_result_missing(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅写入结果缺失",
        context=f"chat_id={chat_id} title={title} year={year or '-'} media_kind={media_kind} 原因={reason}",
        fix_hint="检查 bt_subscription_item 插入查询返回是否仍带有完整结果；当前会按写入失败处理，避免把缺失真相误判成“已成功添加”。",
    )


def _log_bt_subscription_add_item_missing_after_insert(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅写入后条目缺失",
        context=f"chat_id={chat_id} title={title} year={year or '-'} media_kind={media_kind} 原因={reason}",
        fix_hint="检查 bt_subscription_item 表是否被并发删除或触发器回滚；如需继续添加，请先确认 SQLite 写入后能立即回读该条目。",
    )


def _log_bt_subscription_add_row_corrupted(
    *,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    reason: str,
) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅写入命中坏记录",
        context=f"chat_id={chat_id} title={title} year={year or '-'} media_kind={media_kind} 原因={reason}",
        fix_hint="检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；当前会按写入失败处理，避免把损坏记录误判成可复用旧条目或成功新建条目。",
    )


def _log_bt_subscription_last_seen_update_failed(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅最近资源回写失败",
        context=f"chat_id={chat_id} 条目ID={item.item_id} 类型={item.media_kind} source={source} title={title} 原因={reason}",
        fix_hint="检查 SQLite 是否可写、订阅条目是否仍存在，然后重新执行 btsub run。",
    )


def _log_bt_subscription_last_seen_item_missing(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅最近资源回写条目缺失",
        context=f"chat_id={chat_id} 条目ID={item.item_id} 类型={item.media_kind} source={source} title={title} 原因={reason}",
        fix_hint="检查该订阅条目是否已被删除；如仍需继续追踪，请重新添加后再执行 btsub run。",
    )


def _log_bt_subscription_last_seen_result_missing(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅最近资源回写结果缺失",
        context=f"chat_id={chat_id} 条目ID={item.item_id} 类型={item.media_kind} source={source} title={title} 原因={reason}",
        fix_hint="检查 bt_subscription_item 更新返回是否仍带有明确结果；当前会保留已创建的下载待确认，并提示最近资源真相未更新，避免把持久化缺口误判成普通成功。",
    )


def _log_bt_subscription_last_seen_row_corrupted(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅最近资源回写命中坏记录",
        context=f"chat_id={chat_id} 条目ID={item.item_id} 类型={item.media_kind} source={source} title={title} 原因={reason}",
        fix_hint="检查 bt_subscription_item 表里该 chat 的 id、title、media_kind 等真相字段；当前会保留已创建的下载待确认，并提示最近资源真相未更新，避免把损坏记录误判成普通回写失败。",
    )


def _log_bt_subscription_pending_creation_failed(
    *,
    item: BtSubscriptionItem,
    chat_id: int,
    source: str,
    title: str,
    reason: str,
) -> None:
    _print_bt_subscription_issue(
        title="BT 订阅待确认创建失败",
        context=f"chat_id={chat_id} 条目ID={item.item_id} 类型={item.media_kind} source={source} title={title} 原因={reason}",
        fix_hint="检查 SQLite/approval_record 和 jobs 表写入是否正常，然后重新执行 btsub run。",
    )


def _print_bt_subscription_issue(*, title: str, context: str, fix_hint: str) -> None:
    emit_operational_log(title=title, detail=context, fix_hint=fix_hint)


def _is_bt_subscription_item_row_corrupted_reason(reason: str) -> bool:
    return reason in {
        "bt_subscription_item row identity corrupted after read",
        "bt_subscription_item media kind corrupted after read",
    }


def _is_bt_subscription_chat_list_row_corrupted_reason(reason: str) -> bool:
    return reason == "bt_subscription_item chat identity corrupted in chat list after read"
