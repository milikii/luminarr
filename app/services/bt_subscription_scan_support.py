from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from app.db.bt_subscription_repo import BtSubscriptionItem
from app.services.bt_subscription_repo_support import BtSubscriptionRepoResult

ListSubscriptionItemsFunc = Callable[[], BtSubscriptionRepoResult[Sequence[BtSubscriptionItem]]]
RunSubscriptionItemFunc = Callable[[BtSubscriptionItem], Awaitable[tuple[str | None, bool]]]
LogSubscriptionScanItemsReasonFunc = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class BtSubscriptionRunResult:
    scanned: int
    matched: int
    replies: tuple[str, ...]
    pending_creation_failed: bool = False


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
