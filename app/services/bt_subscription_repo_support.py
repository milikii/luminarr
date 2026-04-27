from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from app.db.bt_subscription_repo import BtSubscriptionItem, BtSubscriptionPersistenceError, BtSubscriptionRepo

_ResultT = TypeVar("_ResultT")


@dataclass(frozen=True, slots=True)
class BtSubscriptionRepoResult(Generic[_ResultT]):
    status: str
    value: _ResultT | None = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def add_subscription_item(
    *,
    repo: BtSubscriptionRepo,
    chat_id: int,
    title: str,
    year: str,
    media_kind: str,
    item_missing_reason: str,
    is_item_row_corrupted_reason: Callable[[str], bool],
) -> BtSubscriptionRepoResult[tuple[BtSubscriptionItem, bool]]:
    return _run_repo_call(
        call=lambda: repo.add_item(
            chat_id=chat_id,
            title=title,
            year=year,
            media_kind=media_kind,
        ),
        result_missing_reason="bt subscription add result missing",
        item_missing_reason=item_missing_reason,
        is_item_row_corrupted_reason=is_item_row_corrupted_reason,
    )


def list_subscription_items(
    *,
    repo: BtSubscriptionRepo,
    chat_id: int,
    result_missing_reason: str,
    is_item_row_corrupted_reason: Callable[[str], bool],
) -> BtSubscriptionRepoResult[Sequence[BtSubscriptionItem]]:
    return _run_repo_call(
        call=lambda: repo.list_items(chat_id=chat_id),
        result_missing_reason=result_missing_reason,
        is_item_row_corrupted_reason=is_item_row_corrupted_reason,
    )


def remove_subscription_item(
    *,
    repo: BtSubscriptionRepo,
    chat_id: int,
    item_id: int,
    is_item_row_corrupted_reason: Callable[[str], bool],
) -> BtSubscriptionRepoResult[bool]:
    return _run_repo_call(
        call=lambda: repo.remove_item(chat_id=chat_id, item_id=item_id),
        result_missing_reason="bt subscription remove result missing",
        is_item_row_corrupted_reason=is_item_row_corrupted_reason,
    )


def clear_subscription_items(
    *,
    repo: BtSubscriptionRepo,
    chat_id: int,
    is_item_row_corrupted_reason: Callable[[str], bool],
) -> BtSubscriptionRepoResult[int]:
    return _run_repo_call(
        call=lambda: repo.clear_items(chat_id=chat_id),
        result_missing_reason="bt subscription clear result missing",
        is_item_row_corrupted_reason=is_item_row_corrupted_reason,
    )


def list_subscription_chat_ids(
    *,
    repo: BtSubscriptionRepo,
    is_chat_list_row_corrupted_reason: Callable[[str], bool],
) -> BtSubscriptionRepoResult[Sequence[int]]:
    return _run_repo_call(
        call=repo.list_chat_ids,
        result_missing_reason="bt subscription chat list result missing",
        is_item_row_corrupted_reason=is_chat_list_row_corrupted_reason,
    )


def update_subscription_last_seen(
    *,
    repo: BtSubscriptionRepo,
    chat_id: int,
    item_id: int,
    source: str,
    title: str,
    item_missing_reason: str,
    result_missing_reason: str,
    is_item_row_corrupted_reason: Callable[[str], bool],
) -> BtSubscriptionRepoResult[bool]:
    return _run_repo_call(
        call=lambda: (
            True
            if repo.update_last_seen(
                chat_id=chat_id,
                item_id=item_id,
                source=source,
                title=title,
            )
            else None
        ),
        result_missing_reason=result_missing_reason,
        item_missing_reason=item_missing_reason,
        is_item_row_corrupted_reason=is_item_row_corrupted_reason,
    )


def _run_repo_call(
    *,
    call: Callable[[], _ResultT | None],
    result_missing_reason: str,
    is_item_row_corrupted_reason: Callable[[str], bool],
    item_missing_reason: str = "",
) -> BtSubscriptionRepoResult[_ResultT]:
    try:
        value = call()
        if value is None:
            raise BtSubscriptionPersistenceError(result_missing_reason)
        return BtSubscriptionRepoResult(status="ok", value=value)
    except BtSubscriptionPersistenceError as error:
        reason = str(error)
        if item_missing_reason and reason == item_missing_reason:
            return BtSubscriptionRepoResult(status="item_missing", reason=reason)
        if reason == result_missing_reason:
            return BtSubscriptionRepoResult(status="result_missing", reason=reason)
        if is_item_row_corrupted_reason(reason):
            return BtSubscriptionRepoResult(status="row_corrupted", reason=reason)
        return BtSubscriptionRepoResult(status="failed", reason=reason)
    except sqlite3.Error as error:
        reason = str(error)
        return BtSubscriptionRepoResult(status="failed", reason=reason)
