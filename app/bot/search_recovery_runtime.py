from __future__ import annotations

import re
from typing import Protocol


class SearchServiceLike(Protocol):
    async def search_and_format(
        self,
        query: str,
        *,
        chat_id: int | None,
        channel: str = "telegram",
    ) -> str: ...


def build_recovery_context(*, query: str, chat_id: int | None) -> dict[str, str]:
    compact_query = re.sub(r"\s+", " ", query.strip())
    if len(compact_query) > 160:
        compact_query = compact_query[:160]
    return {
        "system_base": "telegram_private_chat",
        "project_rules": "parser_first_llm_fallback",
        "current_job_context": compact_query if compact_query else f"chat:{chat_id or 0}",
    }


def is_llm_physical_failure(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code == 413:
        return True

    message = str(error).lower()
    patterns = (
        "413",
        "payload too large",
        "max_output_tokens",
        "maximum context length",
        "context length exceeded",
        "response was truncated",
        "truncated",
    )
    return any(pattern in message for pattern in patterns)


async def search_with_reactive_recovery(
    *,
    search_service: SearchServiceLike,
    query: str,
    chat_id: int | None,
    channel: str = "telegram",
    safe_text: str,
) -> str:
    try:
        return await search_service.search_and_format(query, chat_id=chat_id, channel=channel)
    except RuntimeError as error:
        if not is_llm_physical_failure(error):
            raise

    recovery_context = build_recovery_context(query=query, chat_id=chat_id)
    compact_query = recovery_context["current_job_context"]
    try:
        return await search_service.search_and_format(compact_query, chat_id=chat_id, channel=channel)
    except RuntimeError as error:
        if is_llm_physical_failure(error):
            return safe_text
        raise
