from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.search_recovery_runtime import (
    build_recovery_context,
    is_llm_physical_failure,
    search_with_reactive_recovery,
)


def test_build_recovery_context_trims_and_falls_back_to_chat_id() -> None:
    context = build_recovery_context(query="  dune   dune  ", chat_id=1001)
    empty_context = build_recovery_context(query="   ", chat_id=1001)

    assert context["current_job_context"] == "dune dune"
    assert empty_context["current_job_context"] == "chat:1001"


def test_is_llm_physical_failure_matches_status_code_and_message() -> None:
    assert is_llm_physical_failure(SimpleNamespace(status_code=413))
    assert is_llm_physical_failure(RuntimeError("response was truncated"))
    assert not is_llm_physical_failure(RuntimeError("network timeout"))


def test_search_with_reactive_recovery_retries_once_then_returns_success() -> None:
    search_service = SimpleNamespace(
        search_and_format=AsyncMock(
            side_effect=[RuntimeError("413 Payload Too Large"), "搜索结果：dune"]
        )
    )

    result = asyncio.run(
        search_with_reactive_recovery(
            search_service=search_service,
            query="dune dune dune",
            chat_id=1001,
            channel="telegram",
            safe_text="safe",
        )
    )

    assert result == "搜索结果：dune"
    assert search_service.search_and_format.await_count == 2


def test_search_with_reactive_recovery_returns_safe_text_after_second_physical_failure() -> None:
    search_service = SimpleNamespace(
        search_and_format=AsyncMock(
            side_effect=[
                RuntimeError("max_output_tokens truncated"),
                RuntimeError("response was truncated"),
            ]
        )
    )

    result = asyncio.run(
        search_with_reactive_recovery(
            search_service=search_service,
            query="dune dune dune",
            chat_id=1001,
            channel="telegram",
            safe_text="safe",
        )
    )

    assert result == "safe"


def test_search_with_reactive_recovery_re_raises_non_physical_failure() -> None:
    search_service = SimpleNamespace(
        search_and_format=AsyncMock(side_effect=RuntimeError("tmdb down"))
    )

    with pytest.raises(RuntimeError, match="tmdb down"):
        asyncio.run(
            search_with_reactive_recovery(
                search_service=search_service,
                query="dune",
                chat_id=1001,
                channel="telegram",
                safe_text="safe",
            )
        )


def test_search_with_reactive_recovery_re_raises_non_runtime_failure_without_recovery() -> None:
    search_service = SimpleNamespace(
        search_and_format=AsyncMock(side_effect=ValueError("bad search stub"))
    )

    with pytest.raises(ValueError, match="bad search stub"):
        asyncio.run(
            search_with_reactive_recovery(
                search_service=search_service,
                query="dune",
                chat_id=1001,
                channel="telegram",
                safe_text="safe",
            )
        )

    assert search_service.search_and_format.await_count == 1
