from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.bot.execution_runtime import (
    bt_subscription_policy_action,
    resolve_execution_gate,
    run_sync_with_policy,
    watchlist_policy_action,
)
from app.runtime.execution_policy import (
    ACTION_BT_SUBSCRIPTION_LIST,
    ACTION_BT_SUBSCRIPTION_MUTATION,
    ACTION_BT_SUBSCRIPTION_RUN,
    ACTION_RESET_CANDIDATES,
    ACTION_WATCHLIST_LIST,
    ACTION_WATCHLIST_MUTATION,
    ExecutionGate,
)


def test_resolve_execution_gate_reuses_existing_gate() -> None:
    existing_gate = ExecutionGate()
    bot_data = {"execution_gate": existing_gate}

    resolved_gate = resolve_execution_gate(
        bot_data=bot_data,
        execution_gate_key="execution_gate",
    )

    assert resolved_gate is existing_gate


def test_resolve_execution_gate_persists_created_gate() -> None:
    bot_data: dict[str, object] = {}

    resolved_gate = resolve_execution_gate(
        bot_data=bot_data,
        execution_gate_key="execution_gate",
    )

    assert isinstance(resolved_gate, ExecutionGate)
    assert bot_data["execution_gate"] is resolved_gate


def test_run_sync_with_policy_runs_sync_operation() -> None:
    calls: list[str] = []

    result = asyncio.run(
        run_sync_with_policy(
            ExecutionGate(),
            ACTION_RESET_CANDIDATES,
            lambda: calls.append("called") or "done",
        )
    )

    assert result == "done"
    assert calls == ["called"]


def test_policy_action_helpers_map_expected_actions() -> None:
    assert watchlist_policy_action("list") == ACTION_WATCHLIST_LIST
    assert watchlist_policy_action("add") == ACTION_WATCHLIST_MUTATION
    assert watchlist_policy_action("sync") == ACTION_WATCHLIST_MUTATION
    assert bt_subscription_policy_action(SimpleNamespace(action="list")) == ACTION_BT_SUBSCRIPTION_LIST
    assert bt_subscription_policy_action(SimpleNamespace(action="run")) == ACTION_BT_SUBSCRIPTION_RUN
    assert bt_subscription_policy_action(SimpleNamespace(action="add")) == ACTION_BT_SUBSCRIPTION_MUTATION
