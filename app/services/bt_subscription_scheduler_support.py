from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from app.services.bt_subscription_repo_support import BtSubscriptionRepoResult
from app.services.bt_subscription_scan_support import BtSubscriptionRunResult

ListSubscriptionChatIdsFunc = Callable[[], BtSubscriptionRepoResult[Sequence[int]]]
ScanSubscriptionChatFunc = Callable[[int], Awaitable[BtSubscriptionRunResult | None]]
FormatSubscriptionNotificationFunc = Callable[[BtSubscriptionRunResult], str]
LogSubscriptionSchedulerReasonFunc = Callable[[str], None]


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
