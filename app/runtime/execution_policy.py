from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

ACTION_SEARCH_MEDIA = "search_media"
ACTION_GET_DOWNLOAD_STATUS = "get_download_status"
ACTION_WATCHLIST_LIST = "watchlist_list"
ACTION_WATCHLIST_MUTATION = "watchlist_mutation"
ACTION_ADD_TO_DOWNLOADER = "add_to_downloader"
ACTION_CONFIRM_ADD_TO_DOWNLOADER = "confirm_add_to_downloader"
ACTION_IMPORT_TO_LIBRARY = "import_to_library"
ACTION_CONFIRM_IMPORT_TO_LIBRARY = "confirm_import_to_library"
ACTION_CANCEL_PENDING_APPROVAL = "cancel_pending_approval"
ACTION_RESET_CLARIFICATION = "reset_clarification"
ACTION_RESET_CANDIDATES = "reset_candidates"

READ_ONLY_ACTIONS = frozenset(
    {
        ACTION_SEARCH_MEDIA,
        ACTION_GET_DOWNLOAD_STATUS,
        ACTION_WATCHLIST_LIST,
    }
)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    action: str
    concurrency_safe: bool


def resolve_execution_policy(action: str) -> ExecutionPolicy:
    cleaned_action = action.strip()
    return ExecutionPolicy(
        action=cleaned_action,
        concurrency_safe=cleaned_action in READ_ONLY_ACTIONS,
    )


class ExecutionGate:
    """Allows read-only actions to run directly and serializes side-effect actions."""

    def __init__(self) -> None:
        self._side_effect_lock = asyncio.Lock()

    async def run(self, action: str, operation: Callable[[], Awaitable[T]]) -> T:
        policy = resolve_execution_policy(action)
        if policy.concurrency_safe:
            return await operation()

        async with self._side_effect_lock:
            return await operation()

