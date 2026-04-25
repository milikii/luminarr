from __future__ import annotations

from collections.abc import Callable

from app.db.bt_subscription_repo import BtSubscriptionRepo
from app.services.bt_subscription_repo_support import update_subscription_last_seen

LogSubscriptionLastSeenReasonFunc = Callable[[str], None]


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
