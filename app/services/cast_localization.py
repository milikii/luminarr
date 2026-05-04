from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass

from app.services.subtitle_translation_support import _request_subtitle_chat_completion

LookupCastLocalizationFunc = Callable[
    ["CastLocalizationInput"],
    Awaitable[tuple["CastLocalizationMatch", ...]],
]


@dataclass(frozen=True, slots=True)
class CastLocalizationInput:
    """Resolved TMDB cast truth prepared for optional Chinese localization."""

    title: str
    original_title: str
    year: str
    tmdb_id: str
    cast_truth: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class CastLocalizationMatch:
    """Best-effort localized cast text for one TMDB cast row."""

    cast_id: str
    order: int
    original_name: str = ""
    localized_name: str = ""
    localized_character: str = ""


class CastLocalizationService:
    """Thin seam for optional cast text localization providers."""

    def __init__(
        self,
        lookup_func: LookupCastLocalizationFunc | None,
    ) -> None:
        self._lookup_func = lookup_func

    async def localize(
        self,
        localization_input: CastLocalizationInput,
    ) -> tuple[CastLocalizationMatch, ...]:
        """Return localized cast text matches or an empty result when disabled."""
        if self._lookup_func is None:
            return ()
        return await self._lookup_func(localization_input)


class AICastLocalizationService(CastLocalizationService):
    """OpenAI-compatible cast text localization supplement."""

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        timeout_seconds: float = 60.0,
        proxy_url: str = "",
        request_chat_completion_func: Callable[[str, dict[str, object]], str] | None = None,
    ) -> None:
        super().__init__(None)
        self._api_key = api_key.strip()
        self._base_url = (base_url.strip() or "https://api.openai.com/v1").rstrip("/")
        self._model = model.strip() or "gpt-5.4"
        self._timeout_seconds = max(10.0, timeout_seconds)
        self._proxy_url = proxy_url.strip()
        self._request_chat_completion_func = request_chat_completion_func

    async def localize(
        self,
        localization_input: CastLocalizationInput,
    ) -> tuple[CastLocalizationMatch, ...]:
        """Best-effort localize cast rows that still lack Chinese text."""
        if not self._api_key:
            return ()
        cast_rows = _build_pending_cast_rows(localization_input.cast_truth)
        if not cast_rows:
            return ()
        system_prompt, user_payload = _build_cast_localization_payload(
            localization_input=localization_input,
            cast_rows=cast_rows,
        )
        if self._request_chat_completion_func is not None:
            response_text = self._request_chat_completion_func(system_prompt, user_payload)
        else:
            response_text = await asyncio.to_thread(
                _request_subtitle_chat_completion,
                api_key=self._api_key,
                base_url=self._base_url,
                model=self._model,
                timeout_seconds=self._timeout_seconds,
                proxy_url=self._proxy_url,
                system_prompt=system_prompt,
                user_payload=user_payload,
            )
        return _parse_cast_localization_results(response_text, cast_rows=cast_rows)


def _build_pending_cast_rows(
    cast_truth: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    cast_rows: list[dict[str, object]] = []
    for index, cast_member in enumerate(cast_truth):
        cast_id = _clean_text(cast_member.get("id"))
        if not cast_id:
            continue
        name = _clean_text(cast_member.get("name"))
        character = _clean_text(cast_member.get("character"))
        if _contains_cjk(name) and _contains_cjk(character):
            continue
        order_value = cast_member.get("order")
        order = order_value if isinstance(order_value, int) else index
        cast_rows.append(
            {
                "id": cast_id,
                "order": order,
                "name": name,
                "original_name": _clean_text(cast_member.get("original_name")),
                "character": character,
                "original_character": _clean_text(cast_member.get("original_character")),
            }
        )
    return tuple(cast_rows)


def _build_cast_localization_payload(
    *,
    localization_input: CastLocalizationInput,
    cast_rows: Sequence[Mapping[str, object]],
) -> tuple[str, dict[str, object]]:
    system_prompt = (
        "你是影视 metadata 的演员中文化助手。"
        "只补演员名和角色名的简体中文，不得编造人物身份、角色关系或额外字段。"
        "演员名要比角色名更保守：只有高把握时才填写中文名，没把握时留空。"
        "角色名有把握再自然翻译，没把握时留空。"
        "必须保留输入里的 id 对齐，只返回 JSON。"
    )
    user_payload: dict[str, object] = {
        "title": localization_input.title,
        "original_title": localization_input.original_title,
        "year": localization_input.year,
        "tmdb_id": localization_input.tmdb_id,
        "cast": [dict(row) for row in cast_rows],
        "rules": {
            "target_language": "zh-CN",
            "actor_name_policy": "high-confidence-only; otherwise empty string",
            "character_policy": "translate naturally when confident; otherwise empty string",
            "return_json_only": True,
            "json_schema": {
                "cast": [
                    {
                        "id": "TMDB cast id string",
                        "localized_name": "Chinese actor name or empty string",
                        "localized_character": "Chinese role name or empty string",
                    }
                ]
            },
        },
    }
    return system_prompt, user_payload


def _parse_cast_localization_results(
    response_text: str,
    *,
    cast_rows: Sequence[Mapping[str, object]],
) -> tuple[CastLocalizationMatch, ...]:
    try:
        payload = json.loads(response_text)
    except ValueError as exc:
        raise RuntimeError(f"演员中文化响应不是合法 JSON：{exc}") from exc
    items = payload.get("cast")
    if not isinstance(items, list):
        raise RuntimeError("演员中文化响应缺少 cast 数组。")
    row_by_cast_id = {_clean_text(row.get("id")): row for row in cast_rows if _clean_text(row.get("id"))}
    matches: list[CastLocalizationMatch] = []
    seen_cast_ids: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        cast_id = _clean_text(item.get("id"))
        if not cast_id or cast_id in seen_cast_ids:
            continue
        source_row = row_by_cast_id.get(cast_id)
        if source_row is None:
            continue
        order_value = source_row.get("order")
        order = order_value if isinstance(order_value, int) else 0
        matches.append(
            CastLocalizationMatch(
                cast_id=cast_id,
                order=order,
                original_name=_clean_text(source_row.get("original_name")),
                localized_name=_clean_text(item.get("localized_name")),
                localized_character=_clean_text(item.get("localized_character")),
            )
        )
        seen_cast_ids.add(cast_id)
    return tuple(matches)


def _clean_text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _contains_cjk(value: str) -> bool:
    return re.search(r"[\u4e00-\u9fff]", value) is not None
