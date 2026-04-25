from __future__ import annotations

import asyncio

from app.services.bt_subscription_repo_support import BtSubscriptionRepoResult
from app.services.bt_subscription_scan_support import BtSubscriptionRunResult
from app.services.bt_subscription_scheduler_support import (
    collect_bt_subscription_scheduler_notifications,
)


def test_collect_bt_subscription_scheduler_notifications_returns_none_for_result_missing() -> None:
    reasons: list[tuple[str, str]] = []

    notifications = asyncio.run(
        collect_bt_subscription_scheduler_notifications(
            list_chat_ids=lambda: BtSubscriptionRepoResult(
                status="result_missing",
                reason="bt subscription chat list result missing",
            ),
            scan_chat=_unexpected_scan_chat,
            format_notification=lambda result: str(result),
            log_chat_ids_failed=lambda reason: reasons.append(("failed", reason)),
            log_chat_ids_result_missing=lambda reason: reasons.append(("result_missing", reason)),
            log_chat_ids_row_corrupted=lambda reason: reasons.append(("row_corrupted", reason)),
        )
    )

    assert notifications is None
    assert reasons == [("result_missing", "bt subscription chat list result missing")]


def test_collect_bt_subscription_scheduler_notifications_keeps_successful_notifications_when_some_chats_fail() -> None:
    async def _scan_chat(chat_id: int) -> BtSubscriptionRunResult | None:
        if chat_id == 1001:
            return None
        return BtSubscriptionRunResult(
            scanned=1,
            matched=1,
            replies=("下载待确认：Frieren S01E01 1080p",),
        )

    notifications = asyncio.run(
        collect_bt_subscription_scheduler_notifications(
            list_chat_ids=lambda: BtSubscriptionRepoResult(status="ok", value=(1001, 1002)),
            scan_chat=_scan_chat,
            format_notification=lambda result: f"matched={result.matched}",
            log_chat_ids_failed=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
            log_chat_ids_result_missing=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
            log_chat_ids_row_corrupted=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        )
    )

    assert notifications == ((1002, "matched=1"),)


def test_collect_bt_subscription_scheduler_notifications_returns_none_when_all_scans_fail() -> None:
    async def _scan_chat(_: int) -> BtSubscriptionRunResult | None:
        return BtSubscriptionRunResult(scanned=1, matched=0, replies=(), pending_creation_failed=True)

    notifications = asyncio.run(
        collect_bt_subscription_scheduler_notifications(
            list_chat_ids=lambda: BtSubscriptionRepoResult(status="ok", value=(1001,)),
            scan_chat=_scan_chat,
            format_notification=lambda result: f"matched={result.matched}",
            log_chat_ids_failed=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
            log_chat_ids_result_missing=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
            log_chat_ids_row_corrupted=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        )
    )

    assert notifications is None


async def _unexpected_scan_chat(_: int) -> BtSubscriptionRunResult | None:
    raise AssertionError("scan_chat should not be called")
