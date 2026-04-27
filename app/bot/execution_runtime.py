from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import TypeVar

from app.runtime.execution_policy import (
    ACTION_BT_SUBSCRIPTION_LIST,
    ACTION_BT_SUBSCRIPTION_MUTATION,
    ACTION_BT_SUBSCRIPTION_RUN,
    ACTION_WATCHLIST_LIST,
    ACTION_WATCHLIST_MUTATION,
    ExecutionGate,
)
from app.services.manage_bt_subscription import BtSubscriptionCommand

T = TypeVar("T")


def resolve_execution_gate(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate_key: str,
) -> ExecutionGate:
    gate = bot_data.get(execution_gate_key)
    if isinstance(gate, ExecutionGate):
        return gate
    gate = ExecutionGate()
    bot_data[execution_gate_key] = gate
    return gate


async def run_sync_with_policy(
    gate: ExecutionGate,
    action: str,
    operation: Callable[[], T],
) -> T:
    async def _runner() -> T:
        return operation()

    return await gate.run(action, _runner)


def watchlist_policy_action(action: str) -> str:
    if action == "list":
        return ACTION_WATCHLIST_LIST
    return ACTION_WATCHLIST_MUTATION


def bt_subscription_policy_action(command: BtSubscriptionCommand) -> str:
    if command.action == "list":
        return ACTION_BT_SUBSCRIPTION_LIST
    if command.action == "run":
        return ACTION_BT_SUBSCRIPTION_RUN
    return ACTION_BT_SUBSCRIPTION_MUTATION
