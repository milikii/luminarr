from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.db.bt_subscription_repo import BtSubscriptionItem
from app.services.add_to_downloader import ADD_PENDING_STATE_UNAVAILABLE_TEXT
from app.services.bt_subscription_command import bt_subscription_media_kind_label

SearchSubscriptionResultsFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
ResolveSubscriptionCandidateFunc = Callable[[Sequence[Mapping[str, Any]], BtSubscriptionItem], tuple[str, str] | None]
CreateSubscriptionPendingFunc = Callable[[str, str], Awaitable[str]]
UpdateSubscriptionLastSeenStatusFunc = Callable[[str, str], str]
LogSubscriptionScanErrorFunc = Callable[[str, Exception], None]
LogSubscriptionPendingCreationFailedFunc = Callable[[str, str, str], None]


@dataclass(frozen=True, slots=True)
class BtSubscriptionItemDispatchResult:
    reply: str | None
    pending_creation_failed: bool = False


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
    except Exception as error:
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

    year_text = item.year if item.year else "-"
    reply = (
        f"BT 订阅命中新资源：{item.title} ({year_text})\n"
        f"类型: {bt_subscription_media_kind_label(item.media_kind)}\n"
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
