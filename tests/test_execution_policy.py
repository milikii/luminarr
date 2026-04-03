from __future__ import annotations

from app.runtime.execution_policy import (
    ACTION_BT_SUBSCRIPTION_LIST,
    ACTION_BT_SUBSCRIPTION_RUN,
    ACTION_GET_DOWNLOAD_STATUS,
    ACTION_SEARCH_MEDIA,
    ACTION_WATCHLIST_LIST,
    resolve_execution_policy,
)


def test_status_action_is_not_concurrency_safe_after_auto_import_baseline() -> None:
    status_policy = resolve_execution_policy(ACTION_GET_DOWNLOAD_STATUS)
    search_policy = resolve_execution_policy(ACTION_SEARCH_MEDIA)
    watchlist_policy = resolve_execution_policy(ACTION_WATCHLIST_LIST)
    bt_subscription_list_policy = resolve_execution_policy(ACTION_BT_SUBSCRIPTION_LIST)
    bt_subscription_run_policy = resolve_execution_policy(ACTION_BT_SUBSCRIPTION_RUN)

    assert status_policy.concurrency_safe is False
    assert search_policy.concurrency_safe is True
    assert watchlist_policy.concurrency_safe is True
    assert bt_subscription_list_policy.concurrency_safe is True
    assert bt_subscription_run_policy.concurrency_safe is False
