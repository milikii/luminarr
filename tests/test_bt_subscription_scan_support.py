from __future__ import annotations

import asyncio

from app.db.bt_subscription_repo import BtSubscriptionItem
from app.services.bt_subscription_repo_support import BtSubscriptionRepoResult
from app.services.manage_bt_subscription import (
    BtSubscriptionRunResult,
    format_bt_subscription_run_result,
    scan_bt_subscription_items,
)


def test_scan_bt_subscription_items_aggregates_reply_and_pending_creation_state() -> None:
    item_one = _make_bt_subscription_item(item_id=1, title="葬送的芙莉莲")
    item_two = _make_bt_subscription_item(item_id=2, title="沙丘", media_kind="movie")

    async def _run_for_item(item: BtSubscriptionItem) -> tuple[str | None, bool]:
        if item.item_id == 1:
            return ("命中资源: Frieren S01E01 1080p", False)
        return (None, True)

    result = asyncio.run(
        scan_bt_subscription_items(
            list_items=lambda: BtSubscriptionRepoResult(status="ok", value=(item_one, item_two)),
            run_for_item=_run_for_item,
            log_items_failed=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
            log_items_result_missing=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
            log_items_row_corrupted=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        )
    )

    assert result == BtSubscriptionRunResult(
        scanned=2,
        matched=1,
        replies=("命中资源: Frieren S01E01 1080p",),
        pending_creation_failed=True,
    )


def test_scan_bt_subscription_items_returns_empty_result_when_no_items() -> None:
    result = asyncio.run(
        scan_bt_subscription_items(
            list_items=lambda: BtSubscriptionRepoResult(status="ok", value=()),
            run_for_item=_unexpected_run_for_item,
            log_items_failed=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
            log_items_result_missing=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
            log_items_row_corrupted=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
        )
    )

    assert result == BtSubscriptionRunResult(scanned=0, matched=0, replies=())


def test_scan_bt_subscription_items_routes_result_missing_reason_to_specific_logger() -> None:
    reasons: list[tuple[str, str]] = []

    result = asyncio.run(
        scan_bt_subscription_items(
            list_items=lambda: BtSubscriptionRepoResult(
                status="result_missing",
                reason="bt subscription scan items result missing",
            ),
            run_for_item=_unexpected_run_for_item,
            log_items_failed=lambda reason: reasons.append(("failed", reason)),
            log_items_result_missing=lambda reason: reasons.append(("result_missing", reason)),
            log_items_row_corrupted=lambda reason: reasons.append(("row_corrupted", reason)),
        )
    )

    assert result is None
    assert reasons == [("result_missing", "bt subscription scan items result missing")]


def test_format_bt_subscription_run_result_includes_reply_body_and_warning() -> None:
    formatted = format_bt_subscription_run_result(
        result=BtSubscriptionRunResult(
            scanned=2,
            matched=1,
            replies=("下载待确认：Frieren S01E01 1080p",),
            pending_creation_failed=True,
        ),
        run_done_template="BT 订阅扫描完成：共扫描 {scanned} 条，命中新资源 {matched} 条。",
        run_no_new_template="BT 订阅扫描完成：共扫描 {scanned} 条，当前没有新资源。",
        pending_creation_warning_text="注意：本轮有命中的 BT 订阅未能创建下载待确认。",
    )

    assert formatted == (
        "BT 订阅扫描完成：共扫描 2 条，命中新资源 1 条。\n\n"
        "下载待确认：Frieren S01E01 1080p\n\n"
        "注意：本轮有命中的 BT 订阅未能创建下载待确认。"
    )


async def _unexpected_run_for_item(_: BtSubscriptionItem) -> tuple[str | None, bool]:
    raise AssertionError("run_for_item should not be called")


def _make_bt_subscription_item(
    *,
    item_id: int,
    title: str,
    media_kind: str = "anime",
) -> BtSubscriptionItem:
    return BtSubscriptionItem(
        item_id=item_id,
        chat_id=1001,
        title=title,
        year="2023",
        media_kind=media_kind,
        last_seen_source="",
        last_seen_title="",
        created_at="2026-04-19 00:00:00",
        updated_at="2026-04-19 00:00:00",
    )
